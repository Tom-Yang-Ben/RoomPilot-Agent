-- RoomPilot official 9,350-item PostgreSQL schema.
-- Source of truth:
--   backend/catalog/data/furniture_catalog_cloud_9350.json
--   backend/catalog/data/manifests/glb_upload_all_result.csv

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS catalog_items (
    item_id              TEXT PRIMARY KEY,
    name_en              TEXT NOT NULL,
    name_zh              TEXT NOT NULL,
    category_zh          TEXT NOT NULL,
    type_code            TEXT NOT NULL,
    source               TEXT NOT NULL,
    source_group         TEXT,
    width_cm             NUMERIC(10, 3),
    depth_cm             NUMERIC(10, 3),
    height_cm            NUMERIC(10, 3),
    materials            TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    colors               TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    primary_style        TEXT,
    style_candidates     JSONB NOT NULL DEFAULT '[]'::JSONB,
    placement_metadata   JSONB NOT NULL DEFAULT '{}'::JSONB,
    legacy_enrichment_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    search_text          TEXT NOT NULL DEFAULT '',
    raw_data             JSONB NOT NULL,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT catalog_items_width_positive
        CHECK (width_cm IS NULL OR width_cm > 0),
    CONSTRAINT catalog_items_depth_positive
        CHECK (depth_cm IS NULL OR depth_cm > 0),
    CONSTRAINT catalog_items_height_positive
        CHECK (height_cm IS NULL OR height_cm > 0)
);

CREATE TABLE IF NOT EXISTS glb_assets (
    item_id               TEXT PRIMARY KEY
                          REFERENCES catalog_items(item_id) ON DELETE CASCADE,
    manifest_version      TEXT,
    object_key            TEXT NOT NULL UNIQUE,
    original_glb_path     TEXT,
    file_size_bytes       BIGINT,
    sha256                TEXT,
    validation_status     TEXT,
    upload_status         TEXT NOT NULL,
    s3_etag               TEXT,
    s3_uri                TEXT,
    s3_https_url          TEXT,
    delivery_url          TEXT NOT NULL,
    delivery_url_type     TEXT,
    uploaded_at           TIMESTAMPTZ,
    s3_last_modified      TIMESTAMPTZ,
    raw_upload_result     JSONB NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT glb_assets_delivery_https
        CHECK (delivery_url LIKE 'https://%')
);

CREATE TABLE IF NOT EXISTS catalog_import_batches (
    batch_key             TEXT PRIMARY KEY,
    catalog_filename      TEXT NOT NULL,
    manifest_filename     TEXT NOT NULL,
    catalog_rows          INTEGER NOT NULL,
    asset_rows            INTEGER NOT NULL,
    style_enriched_rows   INTEGER NOT NULL DEFAULT 0,
    pruned_rows           INTEGER NOT NULL DEFAULT 0,
    imported_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_catalog_items_type
    ON catalog_items(type_code);
CREATE INDEX IF NOT EXISTS idx_catalog_items_source
    ON catalog_items(source);
CREATE INDEX IF NOT EXISTS idx_catalog_items_primary_style
    ON catalog_items(primary_style);
CREATE INDEX IF NOT EXISTS idx_catalog_items_active
    ON catalog_items(is_active);
CREATE INDEX IF NOT EXISTS idx_catalog_items_materials
    ON catalog_items USING GIN(materials);
CREATE INDEX IF NOT EXISTS idx_catalog_items_colors
    ON catalog_items USING GIN(colors);
CREATE INDEX IF NOT EXISTS idx_catalog_items_styles
    ON catalog_items USING GIN(style_candidates);
CREATE INDEX IF NOT EXISTS idx_catalog_items_search
    ON catalog_items USING GIN(search_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_glb_assets_upload_status
    ON glb_assets(upload_status);

CREATE OR REPLACE VIEW official_furniture_with_glb AS
SELECT
    item.item_id,
    item.name_en,
    item.name_zh,
    item.category_zh,
    item.type_code,
    item.source,
    item.width_cm,
    item.depth_cm,
    item.height_cm,
    item.materials,
    item.colors,
    item.primary_style,
    item.style_candidates,
    item.placement_metadata,
    asset.delivery_url AS glb_url,
    asset.object_key,
    asset.upload_status
FROM catalog_items AS item
JOIN glb_assets AS asset USING (item_id)
WHERE item.is_active
  AND asset.upload_status IN (
      'uploaded',
      'already_exists',
      'complete',
      'completed',
      'success',
      'skipped_existing'
  );
