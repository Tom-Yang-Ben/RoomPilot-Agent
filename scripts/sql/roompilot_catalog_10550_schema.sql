-- RoomPilot PostgreSQL schema
-- 適用資料：家具／家電 catalog + GLB manifest + GLB upload result
-- 建議先在測試資料庫執行，再正式匯入。
-- 本檔只建立目標資料庫內的 schema；首次建置請用匯入器的 --create-database。


CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. 功能群組：穩定的第一層分類。
CREATE TABLE IF NOT EXISTS item_roles (
    role_code      TEXT PRIMARY KEY,
    name_zh        TEXT NOT NULL UNIQUE,
    name_en        TEXT NOT NULL,
    sort_order     SMALLINT NOT NULL DEFAULT 0,
    item_count     INTEGER NOT NULL DEFAULT 0 CHECK (item_count >= 0),
    type_count     INTEGER NOT NULL DEFAULT 0 CHECK (type_count >= 0),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO item_roles (role_code, name_zh, name_en, sort_order)
VALUES
    ('primary_seating',      '主座位',   'Primary seating',      10),
    ('secondary_seating',    '輔助座位', 'Secondary seating',    20),
    ('surface',              '桌面',     'Surface',              30),
    ('storage',              '收納',     'Storage',              40),
    ('sleeping',             '睡眠',     'Sleeping',             50),
    ('lighting',             '照明',     'Lighting',             60),
    ('decor',                '裝飾',     'Decor',                70),
    ('soft_furnishing',      '軟裝',     'Soft furnishing',      80),
    ('appliance',            '家電',     'Appliance',            90),
    ('outdoor',              '戶外',     'Outdoor',             100),
    ('circulation_support',  '動線輔助', 'Circulation support', 110)
ON CONFLICT (role_code) DO UPDATE SET
    name_zh = EXCLUDED.name_zh,
    name_en = EXCLUDED.name_en,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

-- 2. 葉節點類型：使用穩定英文 slug 當主鍵，例如 bed-frame、wall-lamp。
-- source_categories 保存原始資料中出現過的分類名稱，方便追查分類雜訊。
CREATE TABLE IF NOT EXISTS item_types (
    type_code          TEXT PRIMARY KEY,
    role_code          TEXT NOT NULL REFERENCES item_roles(role_code),
    canonical_name_zh  TEXT NOT NULL,
    canonical_name_en  TEXT NOT NULL,
    source_categories  TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    source_type_codes  TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    source_category_variants JSONB NOT NULL DEFAULT '[]'::JSONB,
    sources             TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    kinds               TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    item_count         INTEGER NOT NULL DEFAULT 0 CHECK (item_count >= 0),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. 主資料表。
-- 名稱採 catalog_items，而不是 furniture_items，因為目前資料還包含家電、燈具、地毯與裝飾品。
CREATE TABLE IF NOT EXISTS catalog_items (
    item_id             TEXT PRIMARY KEY,
    name_en             TEXT NOT NULL,
    name_zh             TEXT,
    display_name_zh     TEXT,

    type_code           TEXT NOT NULL REFERENCES item_types(type_code),
    role_code           TEXT NOT NULL REFERENCES item_roles(role_code),
    source_type_code    TEXT NOT NULL,
    source_role_zh      TEXT NOT NULL,
    source_category     TEXT NOT NULL,
    canonical_category_zh TEXT NOT NULL,

    kind                TEXT NOT NULL,
    source              TEXT NOT NULL,
    source_group        TEXT,
    catalog             TEXT NOT NULL,
    source_dataset      TEXT,
    is_ikea             BOOLEAN NOT NULL DEFAULT FALSE,

    width_cm            NUMERIC(10, 3),
    depth_cm            NUMERIC(10, 3),
    height_cm           NUMERIC(10, 3),
    dimension_review_status TEXT,

    materials           TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    colors              TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

    search_text         TEXT NOT NULL DEFAULT '',
    data_quality_flags  TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    raw_data            JSONB NOT NULL,

    duplicate_group_id  TEXT,
    is_primary_variant  BOOLEAN NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT catalog_items_width_positive
        CHECK (width_cm IS NULL OR width_cm > 0),
    CONSTRAINT catalog_items_depth_positive
        CHECK (depth_cm IS NULL OR depth_cm > 0),
    CONSTRAINT catalog_items_height_positive
        CHECK (height_cm IS NULL OR height_cm > 0),
    CONSTRAINT catalog_items_dimension_review_status_valid
        CHECK (
            dimension_review_status IS NULL
            OR dimension_review_status IN ('needs_review', 'reviewed', 'accepted')
        )
);

-- 既有資料庫執行 CREATE TABLE IF NOT EXISTS 時不會自動新增欄位，故保留可重複執行的 migration。
ALTER TABLE item_roles
    ADD COLUMN IF NOT EXISTS item_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS type_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE item_types
    ADD COLUMN IF NOT EXISTS source_type_codes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    ADD COLUMN IF NOT EXISTS source_category_variants JSONB NOT NULL DEFAULT '[]'::JSONB,
    ADD COLUMN IF NOT EXISTS sources TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    ADD COLUMN IF NOT EXISTS kinds TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

ALTER TABLE catalog_items
    ADD COLUMN IF NOT EXISTS display_name_zh TEXT,
    ADD COLUMN IF NOT EXISTS source_type_code TEXT,
    ADD COLUMN IF NOT EXISTS canonical_category_zh TEXT,
    ADD COLUMN IF NOT EXISTS dimension_review_status TEXT,
    ADD COLUMN IF NOT EXISTS duplicate_group_id TEXT,
    ADD COLUMN IF NOT EXISTS is_primary_variant BOOLEAN NOT NULL DEFAULT TRUE;

-- 4. GLB 資產表。
-- manifest 與 upload_result 有大量重複欄位，因此合併成一張「目前資產狀態」表，
-- 同時保留兩份 raw JSONB 以便稽核。
CREATE TABLE IF NOT EXISTS glb_assets (
    item_id                    TEXT PRIMARY KEY REFERENCES catalog_items(item_id) ON DELETE CASCADE,
    manifest_version           TEXT,

    original_glb_path          TEXT,
    local_file_exists          BOOLEAN,
    file_size_bytes            BIGINT CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0),
    sha256                     TEXT,
    upload_filename            TEXT,

    object_key                 TEXT NOT NULL UNIQUE,
    content_type               TEXT NOT NULL DEFAULT 'model/gltf-binary',

    validation_status          TEXT,
    validation_message         TEXT,
    upload_status              TEXT,
    upload_error               TEXT,

    s3_etag                    TEXT,
    s3_uri                     TEXT,
    s3_https_url               TEXT,
    delivery_url               TEXT,
    delivery_url_type          TEXT,
    temporary_presigned_url    TEXT,
    presigned_expires_at       TIMESTAMPTZ,
    s3_version_id              TEXT,
    uploaded_at                TIMESTAMPTZ,
    s3_last_modified           TIMESTAMPTZ,

    raw_manifest               JSONB NOT NULL,
    raw_upload_result          JSONB NOT NULL,

    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. 每次匯入的摘要與原始 manifest report。
CREATE TABLE IF NOT EXISTS import_batches (
    batch_key              TEXT PRIMARY KEY,
    catalog_filename       TEXT NOT NULL,
    manifest_filename      TEXT NOT NULL,
    upload_result_filename TEXT NOT NULL,
    manifest_report        JSONB,
    catalog_rows           INTEGER NOT NULL,
    asset_rows             INTEGER NOT NULL,
    warning_count          INTEGER NOT NULL DEFAULT 0,
    imported_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 常用查詢索引。
CREATE INDEX IF NOT EXISTS idx_catalog_items_role_code
    ON catalog_items(role_code);
CREATE INDEX IF NOT EXISTS idx_catalog_items_type_code
    ON catalog_items(type_code);
CREATE INDEX IF NOT EXISTS idx_catalog_items_kind
    ON catalog_items(kind);
CREATE INDEX IF NOT EXISTS idx_catalog_items_source
    ON catalog_items(source);
CREATE INDEX IF NOT EXISTS idx_catalog_items_catalog
    ON catalog_items(catalog);
CREATE INDEX IF NOT EXISTS idx_catalog_items_dimensions
    ON catalog_items(width_cm, depth_cm, height_cm);
CREATE INDEX IF NOT EXISTS idx_catalog_items_is_active
    ON catalog_items(is_active);
CREATE INDEX IF NOT EXISTS idx_catalog_items_dimension_review_status
    ON catalog_items(dimension_review_status);
CREATE INDEX IF NOT EXISTS idx_catalog_items_duplicate_group_id
    ON catalog_items(duplicate_group_id)
    WHERE duplicate_group_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_catalog_items_materials_gin
    ON catalog_items USING GIN(materials);
CREATE INDEX IF NOT EXISTS idx_catalog_items_colors_gin
    ON catalog_items USING GIN(colors);
CREATE INDEX IF NOT EXISTS idx_catalog_items_quality_flags_gin
    ON catalog_items USING GIN(data_quality_flags);
CREATE INDEX IF NOT EXISTS idx_catalog_items_search_trgm
    ON catalog_items USING GIN(search_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_glb_assets_upload_status
    ON glb_assets(upload_status);
CREATE INDEX IF NOT EXISTS idx_glb_assets_delivery_url
    ON glb_assets(delivery_url);

-- API 查詢可直接使用此 view，同時拿到標準分類與 CloudFront URL。
CREATE OR REPLACE VIEW catalog_items_with_glb AS
SELECT
    i.item_id,
    i.name_en,
    i.name_zh,
    i.kind,
    i.source,
    i.catalog,
    i.type_code,
    t.canonical_name_zh AS type_name_zh,
    t.canonical_name_en AS type_name_en,
    i.role_code,
    r.name_zh AS role_name_zh,
    r.name_en AS role_name_en,
    i.source_category,
    i.width_cm,
    i.depth_cm,
    i.height_cm,
    i.materials,
    i.colors,
    i.data_quality_flags,
    a.object_key,
    a.delivery_url AS glb_url,
    a.upload_status,
    a.file_size_bytes,
    i.updated_at,
    i.display_name_zh,
    i.source_type_code,
    i.canonical_category_zh,
    i.dimension_review_status,
    i.duplicate_group_id,
    i.is_primary_variant,
    i.is_active
FROM catalog_items i
JOIN item_types t ON t.type_code = i.type_code
JOIN item_roles r ON r.role_code = i.role_code
LEFT JOIN glb_assets a ON a.item_id = i.item_id;

-- 空間配置只使用啟用中且尺寸未標記待複查的資料；未知尺寸仍保留給其他查詢處理。
CREATE OR REPLACE VIEW catalog_items_for_space_planning AS
SELECT *
FROM catalog_items_with_glb
WHERE is_active
  AND dimension_review_status IS DISTINCT FROM 'needs_review'
  AND NOT (
      COALESCE(width_cm < 5, FALSE)
      AND COALESCE(depth_cm < 5, FALSE)
      AND COALESCE(height_cm < 5, FALSE)
  );

