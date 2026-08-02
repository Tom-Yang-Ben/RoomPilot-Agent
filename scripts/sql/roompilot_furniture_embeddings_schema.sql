-- RoomPilot BGE-M3 furniture embedding contract.
-- Development phase: VECTOR has no fixed dimension and no HNSW index.

CREATE SCHEMA IF NOT EXISTS roompilot;
CREATE EXTENSION IF NOT EXISTS vector;

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
        CHECK (vector_dims(embedding) = embedding_dimension),
    CONSTRAINT furniture_embeddings_text_hash_sha256
        CHECK (text_hash ~ '^[0-9a-f]{64}$')
);

-- CREATE TABLE IF NOT EXISTS does not retrofit constraints on installations
-- created by the main catalog schema, so add the hash contract separately.
DO $block$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'furniture_embeddings_text_hash_sha256'
          AND conrelid = 'roompilot.furniture_embeddings'::regclass
    ) THEN
        ALTER TABLE roompilot.furniture_embeddings
            ADD CONSTRAINT furniture_embeddings_text_hash_sha256
            CHECK (text_hash ~ '^[0-9a-f]{64}$');
    END IF;
END
$block$;

CREATE INDEX IF NOT EXISTS idx_furniture_embeddings_item_model
    ON roompilot.furniture_embeddings(item_id, embedding_model);

-- 這個 view 直接投影正式 furniture JSON 已匯入 raw_data 的 RAG 文字與雜湊。
-- 它讓 RAG 組員取得穩定輸入，不需要另建一套家具主表或自行猜 annotation_id。
CREATE OR REPLACE VIEW roompilot.furniture_embedding_source_current AS
SELECT
    item.item_id,
    annotation.annotation_id,
    item.raw_data ->> 'embedded_text' AS embedded_text,
    LOWER(item.raw_data ->> 'text_hash') AS text_hash,
    item.raw_data ->> 'text_format_version' AS text_format_version,
    item.raw_data ->> 'style_primary' AS style_primary,
    item.raw_data ->> 'style_secondary' AS style_secondary,
    item.updated_at,
    -- Keep new columns at the end so CREATE OR REPLACE VIEW can upgrade an
    -- existing installation without renaming its historical updated_at column.
    item.raw_data -> 'chroma_metadata' AS chroma_metadata
FROM roompilot.furniture_items AS item
LEFT JOIN LATERAL (
    SELECT source.annotation_id
    FROM roompilot.furniture_vlm_annotations AS source
    WHERE source.item_id = item.item_id
      AND source.is_current
    ORDER BY source.created_at DESC, source.annotation_id DESC
    LIMIT 1
) AS annotation ON TRUE
WHERE item.kind = 'furniture'
  AND item.is_active
  AND COALESCE(item.raw_data ->> 'embedded_text', '') <> ''
  AND COALESCE(item.raw_data ->> 'text_hash', '') ~ '^[0-9A-Fa-f]{64}$';

COMMENT ON TABLE roompilot.furniture_embeddings IS
    'RAG-generated furniture vectors. The SQL owner owns schema; RAG owns text/vector generation and retrieval quality.';
COMMENT ON VIEW roompilot.furniture_embedding_source_current IS
    'Current 8,076-item active RAG text/hash input projected from the 8,675-item official furniture catalog.';

-- Exact search remains model- and dimension-scoped. Add a fixed-dimension HNSW
-- index only after the team freezes one model, dimension, and distance metric.
CREATE OR REPLACE FUNCTION roompilot.search_furniture_embeddings(
    query_embedding VECTOR,
    query_model VARCHAR,
    match_count INTEGER DEFAULT 20
)
RETURNS TABLE (
    item_id TEXT,
    annotation_id BIGINT,
    embedded_text TEXT,
    cosine_distance DOUBLE PRECISION,
    cosine_similarity DOUBLE PRECISION
)
LANGUAGE SQL
STABLE
PARALLEL SAFE
AS $function$
    SELECT
        embedding.item_id,
        current_source.annotation_id,
        embedding.embedded_text,
        embedding.embedding <=> query_embedding AS cosine_distance,
        1.0 - (embedding.embedding <=> query_embedding) AS cosine_similarity
    FROM roompilot.furniture_embeddings AS embedding
    INNER JOIN roompilot.furniture_embedding_source_current AS current_source
        ON current_source.item_id = embedding.item_id
       AND current_source.text_hash = embedding.text_hash
    WHERE embedding.embedding_model = query_model
      AND vector_dims(embedding.embedding) = vector_dims(query_embedding)
    ORDER BY embedding.embedding <=> query_embedding, embedding.item_id
    LIMIT LEAST(GREATEST(match_count, 1), 100)
$function$;

-- Django RAG runtime search. Hard filters are applied before cosine ordering,
-- while styles and moods intentionally remain soft ranking signals in Python.
CREATE OR REPLACE FUNCTION roompilot.search_furniture_embeddings_filtered(
    query_embedding VECTOR,
    query_model VARCHAR,
    match_count INTEGER DEFAULT 50,
    room_type VARCHAR DEFAULT NULL,
    category_values TEXT[] DEFAULT NULL,
    price_min INTEGER DEFAULT NULL,
    price_max INTEGER DEFAULT NULL,
    max_width_cm NUMERIC DEFAULT NULL,
    max_height_cm NUMERIC DEFAULT NULL,
    item_role VARCHAR DEFAULT NULL,
    item_size_class VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    item_id TEXT,
    annotation_id BIGINT,
    embedded_text TEXT,
    metadata JSONB,
    cosine_distance DOUBLE PRECISION,
    cosine_similarity DOUBLE PRECISION
)
LANGUAGE SQL
STABLE
PARALLEL SAFE
AS $function$
    SELECT
        embedding.item_id,
        current_source.annotation_id,
        embedding.embedded_text,
        current_source.chroma_metadata AS metadata,
        embedding.embedding <=> query_embedding AS cosine_distance,
        1.0 - (embedding.embedding <=> query_embedding) AS cosine_similarity
    FROM roompilot.furniture_embeddings AS embedding
    INNER JOIN roompilot.furniture_embedding_source_current AS current_source
        ON current_source.item_id = embedding.item_id
       AND current_source.text_hash = embedding.text_hash
    WHERE embedding.embedding_model = query_model
      AND vector_dims(embedding.embedding) = vector_dims(query_embedding)
      AND jsonb_typeof(current_source.chroma_metadata) = 'object'
      AND (
          room_type IS NULL
          OR COALESCE(
              (current_source.chroma_metadata ->> ('room_' || room_type))::BOOLEAN,
              FALSE
          )
      )
      AND (
          category_values IS NULL
          OR current_source.chroma_metadata ->> 'category' = ANY(category_values)
      )
      AND (
          price_min IS NULL
          OR NULLIF(current_source.chroma_metadata ->> 'price_twd', '')::NUMERIC >= price_min
      )
      AND (
          price_max IS NULL
          OR NULLIF(current_source.chroma_metadata ->> 'price_twd', '')::NUMERIC <= price_max
      )
      AND (
          max_width_cm IS NULL
          OR NULLIF(current_source.chroma_metadata ->> 'width_cm', '')::NUMERIC <= max_width_cm
      )
      AND (
          max_height_cm IS NULL
          OR NULLIF(current_source.chroma_metadata ->> 'height_cm', '')::NUMERIC <= max_height_cm
      )
      AND (
          item_role IS NULL
          OR current_source.chroma_metadata ->> 'role' = item_role
      )
      AND (
          item_size_class IS NULL
          OR current_source.chroma_metadata ->> 'size_class' = item_size_class
      )
    ORDER BY embedding.embedding <=> query_embedding, embedding.item_id
    LIMIT LEAST(GREATEST(match_count, 1), 100)
$function$;
