-- RoomPilot 8,557 筆官方家具資料 PostgreSQL schema
--
-- 正式資料放在 roompilot schema；每次匯入的原始 JSON/CSV 列放在 staging schema。
-- item_id 是家具、GLB、三視角圖片、VLM 標註與 embedding 共用的核心鍵。

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- pgvector 是選用功能。只有 PostgreSQL 能找到 vector extension 時才啟用；
-- 查不到時仍建立其餘 catalog schema，embedding 表與索引留待安裝後補建。
DO $pgvector_extension$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_available_extensions
        WHERE name = 'vector'
    ) THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS vector';
        RAISE NOTICE 'pgvector 已可使用；將建立 furniture_embeddings。';
    ELSE
        RAISE NOTICE
            'pgvector 尚未安裝；跳過 vector extension、furniture_embeddings 與其索引。';
    END IF;
END;
$pgvector_extension$;

CREATE SCHEMA IF NOT EXISTS roompilot;
CREATE SCHEMA IF NOT EXISTS staging;

-- 1. 家具分類字典（目前官方 catalog 為 64 類）
CREATE TABLE IF NOT EXISTS roompilot.furniture_categories (
    category_id        SERIAL PRIMARY KEY,
    category_code      VARCHAR(100) NOT NULL UNIQUE,
    name_zh            VARCHAR(100) NOT NULL UNIQUE,
    name_en            VARCHAR(100),
    parent_category_id INTEGER REFERENCES roompilot.furniture_categories(category_id),
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. 家具核心主表。URL、風格、房間、VLM 與 embedding 不重複塞在這張表。
CREATE TABLE IF NOT EXISTS roompilot.furniture_items (
    item_id            TEXT PRIMARY KEY,
    category_id        INTEGER REFERENCES roompilot.furniture_categories(category_id),
    source             VARCHAR(30) NOT NULL,
    source_group       VARCHAR(50),
    catalog            VARCHAR(100),
    kind               VARCHAR(50),
    source_type        VARCHAR(100),
    name_en            TEXT NOT NULL,
    name_zh            TEXT,
    primary_color      TEXT,
    colors             TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    primary_material   TEXT,
    materials          TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    width_cm           NUMERIC(10, 2),
    depth_cm           NUMERIC(10, 2),
    height_cm          NUMERIC(10, 2),
    price_twd          INTEGER,
    price_is_estimated BOOLEAN NOT NULL DEFAULT FALSE,
    product_url        TEXT,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    raw_data           JSONB NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT furniture_items_width_positive
        CHECK (width_cm IS NULL OR width_cm > 0),
    CONSTRAINT furniture_items_depth_positive
        CHECK (depth_cm IS NULL OR depth_cm > 0),
    CONSTRAINT furniture_items_height_positive
        CHECK (height_cm IS NULL OR height_cm > 0),
    CONSTRAINT furniture_items_price_nonnegative
        CHECK (price_twd IS NULL OR price_twd >= 0)
);

-- 3. 風格字典（目前為 6 種正式風格）
CREATE TABLE IF NOT EXISTS roompilot.styles (
    style_id    SERIAL PRIMARY KEY,
    style_code  VARCHAR(50) NOT NULL UNIQUE,
    name_zh     VARCHAR(100),
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

-- 4. 家具與主/次風格。實際資料有 1,039 筆主、次風格相同，故以 rank 為鍵保留原始資料。
CREATE TABLE IF NOT EXISTS roompilot.furniture_styles (
    item_id    TEXT NOT NULL
               REFERENCES roompilot.furniture_items(item_id) ON DELETE CASCADE,
    style_id   INTEGER NOT NULL REFERENCES roompilot.styles(style_id),
    style_rank SMALLINT NOT NULL,
    confidence NUMERIC(5, 4),
    PRIMARY KEY (item_id, style_rank),
    CONSTRAINT furniture_styles_rank_valid CHECK (style_rank IN (1, 2)),
    CONSTRAINT furniture_styles_confidence_valid
        CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)
);

-- 5. 房間字典（目前為 9 種）
CREATE TABLE IF NOT EXISTS roompilot.rooms (
    room_id   SERIAL PRIMARY KEY,
    room_code VARCHAR(50) NOT NULL UNIQUE,
    name_zh   VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- 6. 家具可使用房間的多對多關聯
CREATE TABLE IF NOT EXISTS roompilot.furniture_rooms (
    item_id TEXT NOT NULL
            REFERENCES roompilot.furniture_items(item_id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES roompilot.rooms(room_id),
    PRIMARY KEY (item_id, room_id)
);

-- 7. VLM 分析版本表。每個家具只允許一筆 is_current = TRUE。
CREATE TABLE IF NOT EXISTS roompilot.furniture_vlm_annotations (
    annotation_id      BIGSERIAL PRIMARY KEY,
    item_id            TEXT NOT NULL
                       REFERENCES roompilot.furniture_items(item_id) ON DELETE CASCADE,
    annotation_hash    VARCHAR(64) NOT NULL,
    model_name         VARCHAR(100),
    model_version      VARCHAR(100),
    prompt_version     VARCHAR(100),
    object_type_zh     TEXT,
    description        TEXT,
    role               VARCHAR(30),
    visual_weight      VARCHAR(30),
    height_zone        VARCHAR(30),
    size_class         VARCHAR(10),
    pattern            TEXT,
    mood_tags          TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    shape_tags         TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    features           TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    search_keywords    TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    rag_text           TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    confidence         NUMERIC(5, 4),
    description_source VARCHAR(100),
    raw_response       JSONB NOT NULL,
    is_current         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (item_id, annotation_hash),
    CONSTRAINT furniture_vlm_confidence_valid
        CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_current_vlm_annotation
    ON roompilot.furniture_vlm_annotations(item_id)
    WHERE is_current;

-- 8. 雲端資產：每件家具 1 個 GLB，加 front/side/angle-45 三張圖片。
CREATE TABLE IF NOT EXISTS roompilot.furniture_assets (
    asset_id            BIGSERIAL PRIMARY KEY,
    external_id         TEXT NOT NULL UNIQUE,
    item_id             TEXT NOT NULL
                        REFERENCES roompilot.furniture_items(item_id) ON DELETE CASCADE,
    asset_type          VARCHAR(20) NOT NULL,
    view_role           VARCHAR(30),
    source_path         TEXT,
    local_file_exists   BOOLEAN,
    object_key          TEXT NOT NULL UNIQUE,
    bucket_name         TEXT,
    s3_uri              TEXT,
    s3_https_url        TEXT,
    delivery_url        TEXT,
    delivery_url_type   VARCHAR(30),
    content_type        VARCHAR(100),
    file_size_bytes     BIGINT,
    width_px            INTEGER,
    height_px           INTEGER,
    sha256              VARCHAR(64),
    etag                TEXT,
    upload_status       VARCHAR(30),
    validation_status   VARCHAR(30),
    validation_message  TEXT,
    upload_error        TEXT,
    uploaded_at         TIMESTAMPTZ,
    s3_last_modified    TIMESTAMPTZ,
    s3_version_id       TEXT,
    manifest_version    VARCHAR(30),
    raw_manifest        JSONB NOT NULL,
    raw_upload_result   JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT furniture_assets_type_role_valid CHECK (
        (asset_type = 'glb' AND view_role IS NULL)
        OR
        (asset_type = 'image' AND view_role IN ('front', 'side', 'angle-45'))
    ),
    CONSTRAINT furniture_assets_file_size_nonnegative
        CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0),
    CONSTRAINT furniture_assets_width_positive
        CHECK (width_px IS NULL OR width_px > 0),
    CONSTRAINT furniture_assets_height_positive
        CHECK (height_px IS NULL OR height_px > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_furniture_glb
    ON roompilot.furniture_assets(item_id)
    WHERE asset_type = 'glb';

CREATE UNIQUE INDEX IF NOT EXISTS uq_furniture_image_role
    ON roompilot.furniture_assets(item_id, view_role)
    WHERE asset_type = 'image';

-- 9. 選用 RAG embedding。使用動態 SQL，避免未安裝 pgvector 時解析 VECTOR 型別失敗。
DO $furniture_embeddings_table$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_extension
        WHERE extname = 'vector'
    ) THEN
        EXECUTE $embedding_table_sql$
            CREATE TABLE IF NOT EXISTS roompilot.furniture_embeddings (
                embedding_id         BIGSERIAL PRIMARY KEY,
                item_id              TEXT NOT NULL
                                     REFERENCES roompilot.furniture_items(item_id)
                                     ON DELETE CASCADE,
                annotation_id        BIGINT
                                     REFERENCES roompilot.furniture_vlm_annotations(annotation_id)
                                     ON DELETE SET NULL,
                embedding_model      VARCHAR(100) NOT NULL,
                embedding_dimension  INTEGER NOT NULL,
                embedded_text        TEXT NOT NULL,
                text_hash            VARCHAR(64) NOT NULL,
                embedding            VECTOR NOT NULL,
                created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (item_id, embedding_model, text_hash),
                CONSTRAINT furniture_embeddings_dimension_positive
                    CHECK (embedding_dimension > 0),
                CONSTRAINT furniture_embeddings_dimension_matches
                    CHECK (vector_dims(embedding) = embedding_dimension)
            )
        $embedding_table_sql$;
    ELSE
        RAISE NOTICE '未啟用 pgvector，略過 roompilot.furniture_embeddings。';
    END IF;
END;
$furniture_embeddings_table$;

-- 10. 匯入時發現及後續人工建立的資料品質問題
CREATE TABLE IF NOT EXISTS roompilot.furniture_quality_issues (
    issue_id         BIGSERIAL PRIMARY KEY,
    item_id          TEXT NOT NULL
                     REFERENCES roompilot.furniture_items(item_id) ON DELETE CASCADE,
    issue_type       VARCHAR(100) NOT NULL,
    issue_source     VARCHAR(50) NOT NULL DEFAULT 'manual',
    severity         VARCHAR(30),
    current_value    JSONB,
    suggested_value  JSONB,
    status           VARCHAR(30) NOT NULL DEFAULT 'open',
    reviewed_by      VARCHAR(100),
    reviewed_at      TIMESTAMPTZ,
    review_note      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (item_id, issue_type, issue_source),
    CONSTRAINT furniture_quality_severity_valid
        CHECK (severity IS NULL OR severity IN ('low', 'medium', 'high')),
    CONSTRAINT furniture_quality_status_valid
        CHECK (status IN ('open', 'confirmed', 'fixed', 'ignored'))
);

-- Phase 2 管理 API 稽核紀錄。與家具異動寫在同一個 transaction，
-- 不存 Authorization token，並保留軟刪除前後的資料快照。
CREATE TABLE IF NOT EXISTS roompilot.furniture_admin_audit (
    event_id       BIGSERIAL PRIMARY KEY,
    item_id        TEXT NOT NULL,
    action         VARCHAR(30) NOT NULL,
    actor          VARCHAR(100) NOT NULL,
    changed_fields TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    before_data    JSONB,
    after_data     JSONB NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT furniture_admin_audit_action_valid
        CHECK (action IN ('create', 'update', 'soft_delete'))
);

-- 原始來源 staging。batch_key 由五個輸入檔的 SHA-256 產生，可重複執行而不混批。
CREATE TABLE IF NOT EXISTS staging.stg_furniture_catalog (
    batch_key   VARCHAR(64) NOT NULL,
    row_number  INTEGER NOT NULL CHECK (row_number > 0),
    item_id     TEXT NOT NULL,
    source_file TEXT NOT NULL,
    raw_data    JSONB NOT NULL,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (batch_key, row_number),
    UNIQUE (batch_key, item_id)
);

CREATE TABLE IF NOT EXISTS staging.stg_glb_manifest (
    batch_key   VARCHAR(64) NOT NULL,
    row_number  INTEGER NOT NULL CHECK (row_number > 0),
    item_id     TEXT NOT NULL,
    object_key  TEXT,
    source_file TEXT NOT NULL,
    raw_data    JSONB NOT NULL,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (batch_key, row_number),
    UNIQUE (batch_key, item_id)
);

CREATE TABLE IF NOT EXISTS staging.stg_glb_upload_result (
    batch_key   VARCHAR(64) NOT NULL,
    row_number  INTEGER NOT NULL CHECK (row_number > 0),
    item_id     TEXT NOT NULL,
    object_key  TEXT,
    source_file TEXT NOT NULL,
    raw_data    JSONB NOT NULL,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (batch_key, row_number),
    UNIQUE (batch_key, item_id)
);

CREATE TABLE IF NOT EXISTS staging.stg_image_manifest (
    batch_key   VARCHAR(64) NOT NULL,
    row_number  INTEGER NOT NULL CHECK (row_number > 0),
    image_id    TEXT NOT NULL,
    item_id     TEXT NOT NULL,
    view_role   VARCHAR(30),
    object_key  TEXT,
    source_file TEXT NOT NULL,
    raw_data    JSONB NOT NULL,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (batch_key, row_number),
    UNIQUE (batch_key, image_id)
);

CREATE TABLE IF NOT EXISTS staging.stg_image_upload_result (
    batch_key   VARCHAR(64) NOT NULL,
    row_number  INTEGER NOT NULL CHECK (row_number > 0),
    image_id    TEXT NOT NULL,
    item_id     TEXT NOT NULL,
    view_role   VARCHAR(30),
    object_key  TEXT,
    source_file TEXT NOT NULL,
    raw_data    JSONB NOT NULL,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (batch_key, row_number),
    UNIQUE (batch_key, image_id)
);

CREATE INDEX IF NOT EXISTS idx_furniture_items_category
    ON roompilot.furniture_items(category_id);
CREATE INDEX IF NOT EXISTS idx_furniture_items_source
    ON roompilot.furniture_items(source);
CREATE INDEX IF NOT EXISTS idx_furniture_items_active
    ON roompilot.furniture_items(is_active);
CREATE INDEX IF NOT EXISTS idx_furniture_items_name_en_trgm
    ON roompilot.furniture_items USING GIN(name_en gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_furniture_items_name_zh_trgm
    ON roompilot.furniture_items USING GIN(name_zh gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_furniture_styles_style
    ON roompilot.furniture_styles(style_id);
CREATE INDEX IF NOT EXISTS idx_furniture_rooms_room
    ON roompilot.furniture_rooms(room_id);
CREATE INDEX IF NOT EXISTS idx_furniture_assets_item
    ON roompilot.furniture_assets(item_id);
CREATE INDEX IF NOT EXISTS idx_furniture_assets_upload_status
    ON roompilot.furniture_assets(upload_status);
DO $furniture_embeddings_index$
BEGIN
    IF TO_REGCLASS('roompilot.furniture_embeddings') IS NOT NULL THEN
        EXECUTE
            'CREATE INDEX IF NOT EXISTS idx_furniture_embeddings_item_model '
            'ON roompilot.furniture_embeddings(item_id, embedding_model)';
    ELSE
        RAISE NOTICE 'furniture_embeddings 不存在，略過 embedding index。';
    END IF;
END;
$furniture_embeddings_index$;
CREATE INDEX IF NOT EXISTS idx_furniture_quality_open
    ON roompilot.furniture_quality_issues(item_id, severity)
    WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_furniture_admin_audit_item_created
    ON roompilot.furniture_admin_audit(item_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stg_glb_manifest_item
    ON staging.stg_glb_manifest(item_id);
CREATE INDEX IF NOT EXISTS idx_stg_glb_result_item
    ON staging.stg_glb_upload_result(item_id);
CREATE INDEX IF NOT EXISTS idx_stg_image_manifest_item
    ON staging.stg_image_manifest(item_id);
CREATE INDEX IF NOT EXISTS idx_stg_image_result_item
    ON staging.stg_image_upload_result(item_id);

-- API 常用的目前版家具 view；資產 URL 從 furniture_assets 聚合，不重複保存。
CREATE OR REPLACE VIEW roompilot.furniture_catalog_current AS
SELECT
    i.item_id,
    i.name_en,
    i.name_zh,
    c.category_code,
    c.name_zh AS category_name_zh,
    i.source,
    i.source_group,
    i.catalog,
    i.kind,
    i.source_type,
    i.primary_color,
    i.colors,
    i.primary_material,
    i.materials,
    i.width_cm,
    i.depth_cm,
    i.height_cm,
    i.price_twd,
    i.price_is_estimated,
    i.product_url,
    style_data.style_codes,
    room_data.room_codes,
    annotation.object_type_zh,
    annotation.description,
    annotation.rag_text,
    asset_data.glb_url,
    asset_data.front_image_url,
    asset_data.side_image_url,
    asset_data.angle_45_image_url,
    style_data.style_confidences,
    annotation.role,
    annotation.visual_weight,
    annotation.height_zone,
    annotation.size_class,
    annotation.pattern,
    annotation.mood_tags,
    annotation.features,
    annotation.search_keywords,
    (style_data.style_confidences)[1] AS style_confidence,
    annotation.confidence AS annotation_confidence,
    COALESCE(annotation.description_source, 'kai_postgresql_vlm')
        AS style_assignment_source
FROM roompilot.furniture_items AS i
LEFT JOIN roompilot.furniture_categories AS c
    ON c.category_id = i.category_id
LEFT JOIN LATERAL (
    SELECT
        ARRAY_AGG(s.style_code ORDER BY fs.style_rank) AS style_codes,
        ARRAY_AGG(fs.confidence ORDER BY fs.style_rank) AS style_confidences
    FROM roompilot.furniture_styles AS fs
    JOIN roompilot.styles AS s ON s.style_id = fs.style_id
    WHERE fs.item_id = i.item_id
) AS style_data ON TRUE
LEFT JOIN LATERAL (
    SELECT ARRAY_AGG(r.room_code ORDER BY r.room_code) AS room_codes
    FROM roompilot.furniture_rooms AS fr
    JOIN roompilot.rooms AS r ON r.room_id = fr.room_id
    WHERE fr.item_id = i.item_id
) AS room_data ON TRUE
LEFT JOIN roompilot.furniture_vlm_annotations AS annotation
    ON annotation.item_id = i.item_id AND annotation.is_current
LEFT JOIN LATERAL (
    SELECT
        MAX(a.delivery_url) FILTER (WHERE a.asset_type = 'glb') AS glb_url,
        MAX(a.delivery_url) FILTER (
            WHERE a.asset_type = 'image' AND a.view_role = 'front'
        ) AS front_image_url,
        MAX(a.delivery_url) FILTER (
            WHERE a.asset_type = 'image' AND a.view_role = 'side'
        ) AS side_image_url,
        MAX(a.delivery_url) FILTER (
            WHERE a.asset_type = 'image' AND a.view_role = 'angle-45'
        ) AS angle_45_image_url
    FROM roompilot.furniture_assets AS a
    WHERE a.item_id = i.item_id
      AND LOWER(COALESCE(a.upload_status, '')) IN (
          'already_exists', 'complete', 'completed', 'skipped_existing',
          'success', 'uploaded'
      )
      AND LOWER(COALESCE(a.validation_status, 'ready')) IN (
          '', 'ready', 'success', 'valid'
      )
) AS asset_data ON TRUE
WHERE i.is_active;

-- FastAPI 專用的穩定 read model。UI 所需的分類與安全預設集中在 SQL view，
-- repository 只負責查詢；資料庫與目前 UI 均使用相同的 6 種正式風格。
CREATE OR REPLACE VIEW roompilot.furniture_catalog_api_current AS
SELECT
    catalog.*,
    CASE
        WHEN catalog.category_code = 'planter' THEN 'flower-pots-planter'
        ELSE COALESCE(catalog.category_code, catalog.source_type, 'furniture')
    END AS normalized_type,
    CASE
        WHEN catalog.category_code IN (
            'armchair', 'coffee-table', 'fabric-sofa', 'leather-sofa',
            'modular-sofa', 'sofa', 'sofa-bed', 'tv-bench', 'tv-media-furniture'
        ) THEN 'living'
        WHEN catalog.category_code IN (
            'bar-table', 'dining-chair', 'dining-table', 'stool-bench', 'table'
        ) THEN 'dining_kitchen'
        WHEN catalog.category_code IN (
            'bed', 'bed-frame', 'bedside-table', 'mattress', 'pax-wardrobe', 'wardrobe'
        ) THEN 'bedroom'
        WHEN catalog.category_code IN ('desk', 'gaming-chair', 'office-chair', 'work-lamp')
            THEN 'study'
        WHEN catalog.category_code IN (
            'bookcase', 'cabinet-cupboard', 'chests-of-drawer', 'clothes-rack',
            'display-cabinet', 'shelving-unit', 'shoe-cabinet', 'sideboard',
            'storage-boxes-basket', 'storage-furniture', 'storage-solution-system',
            'wall-shelf'
        ) THEN 'storage'
        WHEN catalog.category_code IN (
            'ceiling-lamp', 'decoration', 'door-mat', 'floor-lamp', 'handmade-rug',
            'lamp', 'lamp-shades-base', 'large-medium-rug', 'large-mirror', 'mirror',
            'outdoor-rug', 'pendant-lamp', 'pillow-cushion', 'planter', 'round-rug',
            'runner-small-rug', 'sheepskins-cowhide', 'standing-mirror', 'table-lamp',
            'vase', 'wall-art', 'wall-lamp', 'wall-mirror'
        ) THEN 'soft_decor'
        WHEN 'study' = ANY(COALESCE(catalog.room_codes, ARRAY[]::TEXT[])) THEN 'study'
        WHEN 'bedroom' = ANY(COALESCE(catalog.room_codes, ARRAY[]::TEXT[])) THEN 'bedroom'
        WHEN 'dining_room' = ANY(COALESCE(catalog.room_codes, ARRAY[]::TEXT[]))
            THEN 'dining_kitchen'
        WHEN 'living_room' = ANY(COALESCE(catalog.room_codes, ARRAY[]::TEXT[]))
            THEN 'living'
        ELSE 'soft_decor'
    END AS taxonomy_group,
    CASE
        WHEN catalog.category_code IN (
            'armchair', 'coffee-table', 'fabric-sofa', 'leather-sofa',
            'modular-sofa', 'sofa', 'sofa-bed', 'tv-bench', 'tv-media-furniture'
        ) THEN '客廳家具'
        WHEN catalog.category_code IN (
            'bar-table', 'dining-chair', 'dining-table', 'stool-bench', 'table'
        ) THEN '餐廚家具'
        WHEN catalog.category_code IN (
            'bed', 'bed-frame', 'bedside-table', 'mattress', 'pax-wardrobe', 'wardrobe'
        ) THEN '臥室家具'
        WHEN catalog.category_code IN ('desk', 'gaming-chair', 'office-chair', 'work-lamp')
            THEN '書房家具'
        WHEN catalog.category_code IN (
            'bookcase', 'cabinet-cupboard', 'chests-of-drawer', 'clothes-rack',
            'display-cabinet', 'shelving-unit', 'shoe-cabinet', 'sideboard',
            'storage-boxes-basket', 'storage-furniture', 'storage-solution-system',
            'wall-shelf'
        ) THEN '收納家具'
        WHEN catalog.category_code IN (
            'ceiling-lamp', 'decoration', 'door-mat', 'floor-lamp', 'handmade-rug',
            'lamp', 'lamp-shades-base', 'large-medium-rug', 'large-mirror', 'mirror',
            'outdoor-rug', 'pendant-lamp', 'pillow-cushion', 'planter', 'round-rug',
            'runner-small-rug', 'sheepskins-cowhide', 'standing-mirror', 'table-lamp',
            'vase', 'wall-art', 'wall-lamp', 'wall-mirror'
        ) THEN '軟裝與燈飾'
        WHEN 'study' = ANY(COALESCE(catalog.room_codes, ARRAY[]::TEXT[])) THEN '書房家具'
        WHEN 'bedroom' = ANY(COALESCE(catalog.room_codes, ARRAY[]::TEXT[])) THEN '臥室家具'
        WHEN 'dining_room' = ANY(COALESCE(catalog.room_codes, ARRAY[]::TEXT[]))
            THEN '餐廚家具'
        WHEN 'living_room' = ANY(COALESCE(catalog.room_codes, ARRAY[]::TEXT[]))
            THEN '客廳家具'
        ELSE '軟裝與燈飾'
    END AS taxonomy_group_zh,
    COALESCE(
        catalog.category_name_zh,
        catalog.category_code,
        catalog.source_type,
        'furniture'
    ) AS taxonomy_type_zh,
    COALESCE(
        catalog.category_name_zh,
        catalog.category_code,
        catalog.source_type,
        'furniture'
    ) AS category_label,
    'kai_postgresql'::TEXT AS catalog_scope,
    FALSE AS must_against_wall,
    TRUE AS can_rotate,
    TRUE AS usable_for_moodboard
FROM roompilot.furniture_catalog_current AS catalog;

CREATE OR REPLACE FUNCTION roompilot.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_furniture_categories_updated_at
    ON roompilot.furniture_categories;
CREATE TRIGGER trg_furniture_categories_updated_at
BEFORE UPDATE ON roompilot.furniture_categories
FOR EACH ROW EXECUTE FUNCTION roompilot.set_updated_at();

DROP TRIGGER IF EXISTS trg_furniture_items_updated_at
    ON roompilot.furniture_items;
CREATE TRIGGER trg_furniture_items_updated_at
BEFORE UPDATE ON roompilot.furniture_items
FOR EACH ROW EXECUTE FUNCTION roompilot.set_updated_at();

DROP TRIGGER IF EXISTS trg_furniture_assets_updated_at
    ON roompilot.furniture_assets;
CREATE TRIGGER trg_furniture_assets_updated_at
BEFORE UPDATE ON roompilot.furniture_assets
FOR EACH ROW EXECUTE FUNCTION roompilot.set_updated_at();

DROP TRIGGER IF EXISTS trg_furniture_quality_updated_at
    ON roompilot.furniture_quality_issues;
CREATE TRIGGER trg_furniture_quality_updated_at
BEFORE UPDATE ON roompilot.furniture_quality_issues
FOR EACH ROW EXECUTE FUNCTION roompilot.set_updated_at();
