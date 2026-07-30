-- RoomPilot Phase 4 runtime catalog schema.
-- Keep this schema beside import_runtime_catalogs_to_postgres.py.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS roompilot;

CREATE TABLE IF NOT EXISTS roompilot.runtime_catalog_imports (
    catalog_key     TEXT PRIMARY KEY,
    schema_version  TEXT,
    catalog_version TEXT,
    source_path     TEXT NOT NULL,
    source_sha256   TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::JSONB,
    record_count    INTEGER NOT NULL CHECK (record_count >= 0),
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roompilot.style_cards (
    card_id          TEXT PRIMARY KEY,
    style_id         TEXT NOT NULL,
    style_order      INTEGER NOT NULL CHECK (style_order >= 0),
    card_order       INTEGER NOT NULL CHECK (card_order >= 0),
    style_name_zh    TEXT NOT NULL,
    scene_style_id   TEXT NOT NULL,
    description_zh   TEXT NOT NULL DEFAULT '',
    name_zh          TEXT NOT NULL,
    image_file       TEXT NOT NULL,
    palette_hex      TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    style_payload    JSONB NOT NULL,
    card_payload     JSONB NOT NULL,
    rag_text         TEXT NOT NULL,
    source_sha256    TEXT NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    imported_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (style_id, card_order)
);

CREATE TABLE IF NOT EXISTS roompilot.design_style_profiles (
    style_id       TEXT PRIMARY KEY,
    style_order    INTEGER NOT NULL CHECK (style_order >= 0),
    payload        JSONB NOT NULL,
    source_sha256  TEXT NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    imported_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roompilot.surface_materials (
    surface_id       TEXT PRIMARY KEY,
    name_zh          TEXT NOT NULL,
    material_group   TEXT,
    category         TEXT,
    color_zh         TEXT,
    color_hex        TEXT,
    usage            TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    suitable_styles  TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    texture_url      TEXT,
    preview_url      TEXT,
    payload          JSONB NOT NULL,
    rag_text         TEXT NOT NULL,
    source_sha256    TEXT NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    imported_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roompilot.style_surface_profiles (
    style_id       TEXT PRIMARY KEY,
    payload        JSONB NOT NULL,
    source_sha256  TEXT NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    imported_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roompilot.renovation_cost_sources (
    source_id       TEXT PRIMARY KEY,
    publisher       TEXT NOT NULL,
    title           TEXT,
    url             TEXT NOT NULL,
    retrieved_on    DATE NOT NULL,
    payload         JSONB NOT NULL,
    source_sha256   TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roompilot.renovation_cost_rates (
    work_code       TEXT PRIMARY KEY,
    unit            TEXT NOT NULL,
    low_twd         NUMERIC(14, 2) NOT NULL CHECK (low_twd >= 0),
    base_twd        NUMERIC(14, 2) NOT NULL CHECK (base_twd >= 0),
    high_twd        NUMERIC(14, 2) NOT NULL CHECK (high_twd >= 0),
    source_ids      TEXT[] NOT NULL,
    valid_as_of     DATE,
    payload         JSONB NOT NULL,
    rag_text        TEXT NOT NULL,
    source_sha256   TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (low_twd <= base_twd AND base_twd <= high_twd)
);

CREATE TABLE IF NOT EXISTS roompilot.external_import_quarantine (
    source_kind       TEXT NOT NULL,
    record_id         TEXT NOT NULL,
    quarantine_reason TEXT NOT NULL,
    review_status     TEXT NOT NULL DEFAULT 'quarantined'
                      CHECK (review_status IN ('quarantined', 'approved', 'rejected')),
    catalog_scope     TEXT,
    raw_payload       JSONB NOT NULL,
    source_path       TEXT NOT NULL,
    source_sha256     TEXT NOT NULL,
    record_sha256     TEXT NOT NULL,
    is_current        BOOLEAN NOT NULL DEFAULT TRUE,
    eligible_for_api  BOOLEAN NOT NULL DEFAULT FALSE,
    eligible_for_rag  BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by       TEXT,
    review_note       TEXT,
    reviewed_at       TIMESTAMPTZ,
    imported_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_kind, record_id),
    CONSTRAINT external_quarantine_never_api CHECK (NOT eligible_for_api),
    CONSTRAINT external_quarantine_never_rag CHECK (NOT eligible_for_rag)
);

UPDATE roompilot.external_import_quarantine
SET eligible_for_api = FALSE,
    eligible_for_rag = FALSE
WHERE eligible_for_api OR eligible_for_rag;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'external_quarantine_never_api'
          AND conrelid = 'roompilot.external_import_quarantine'::REGCLASS
    ) THEN
        ALTER TABLE roompilot.external_import_quarantine
            ADD CONSTRAINT external_quarantine_never_api CHECK (NOT eligible_for_api);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'external_quarantine_never_rag'
          AND conrelid = 'roompilot.external_import_quarantine'::REGCLASS
    ) THEN
        ALTER TABLE roompilot.external_import_quarantine
            ADD CONSTRAINT external_quarantine_never_rag CHECK (NOT eligible_for_rag);
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_style_cards_style_order
    ON roompilot.style_cards(style_order, card_order) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_style_cards_rag_trgm
    ON roompilot.style_cards USING GIN(rag_text gin_trgm_ops) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_design_style_profiles_order
    ON roompilot.design_style_profiles(style_order) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_surface_materials_usage
    ON roompilot.surface_materials USING GIN(usage) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_surface_materials_styles
    ON roompilot.surface_materials USING GIN(suitable_styles) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_surface_materials_rag_trgm
    ON roompilot.surface_materials USING GIN(rag_text gin_trgm_ops) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_renovation_cost_rates_rag_trgm
    ON roompilot.renovation_cost_rates USING GIN(rag_text gin_trgm_ops) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_external_quarantine_review
    ON roompilot.external_import_quarantine(source_kind, review_status, is_current);

CREATE OR REPLACE VIEW roompilot.style_cards_current AS
SELECT *
FROM roompilot.style_cards
WHERE is_active;

CREATE OR REPLACE VIEW roompilot.design_style_profiles_current AS
SELECT *
FROM roompilot.design_style_profiles
WHERE is_active;

CREATE OR REPLACE VIEW roompilot.surface_materials_current AS
SELECT *
FROM roompilot.surface_materials
WHERE is_active;

CREATE OR REPLACE VIEW roompilot.renovation_cost_catalog_current AS
SELECT *
FROM roompilot.renovation_cost_rates
WHERE is_active;

CREATE OR REPLACE VIEW roompilot.runtime_catalog_rag_documents AS
SELECT
    'style_card:' || card_id AS document_id,
    'style_card'::TEXT AS document_type,
    name_zh AS title,
    rag_text AS content,
    JSONB_BUILD_OBJECT(
        'card_id', card_id,
        'style_id', style_id,
        'scene_style_id', scene_style_id,
        'palette_hex', TO_JSONB(palette_hex),
        'image_file', image_file
    ) AS metadata
FROM roompilot.style_cards_current
UNION ALL
SELECT
    'surface_material:' || surface_id,
    'surface_material'::TEXT,
    name_zh,
    rag_text,
    JSONB_BUILD_OBJECT(
        'surface_id', surface_id,
        'category', category,
        'material_group', material_group,
        'color_zh', color_zh,
        'usage', TO_JSONB(usage),
        'suitable_styles', TO_JSONB(suitable_styles),
        'texture_url', texture_url,
        'preview_url', preview_url
    )
FROM roompilot.surface_materials_current
UNION ALL
SELECT
    'renovation_cost:' || work_code,
    'renovation_cost'::TEXT,
    work_code,
    rag_text,
    JSONB_BUILD_OBJECT(
        'work_code', work_code,
        'unit', unit,
        'range_twd', JSONB_BUILD_OBJECT('low', low_twd, 'base', base_twd, 'high', high_twd),
        'source_ids', TO_JSONB(source_ids),
        'sources', COALESCE((
            SELECT JSONB_AGG(source.payload ORDER BY source.source_id)
            FROM roompilot.renovation_cost_sources AS source
            WHERE source.is_active AND source.source_id = ANY(rate.source_ids)
        ), '[]'::JSONB),
        'valid_as_of', valid_as_of
    )
FROM roompilot.renovation_cost_catalog_current AS rate;

COMMENT ON VIEW roompilot.runtime_catalog_rag_documents IS
    'Phase 4 RAG evidence for styles, surfaces, and costs. Quarantine is intentionally excluded.';
