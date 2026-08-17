-- Generic, data-free pgvector contract for the public full profile.
-- Catalog rows must be imported through the licensed catalog importer first.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS roompilot;

CREATE TABLE IF NOT EXISTS roompilot.furniture_embeddings (
    embedding_id bigserial PRIMARY KEY,
    item_id text NOT NULL
        REFERENCES roompilot.furniture_catalog(item_id)
        ON DELETE CASCADE,
    annotation_id bigint,
    embedding_model varchar(100) NOT NULL,
    embedding_dimension integer NOT NULL,
    embedded_text text NOT NULL,
    text_hash varchar(64) NOT NULL,
    embedding vector NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (item_id, embedding_model, text_hash),
    CONSTRAINT furniture_embeddings_dimension_positive
        CHECK (embedding_dimension > 0),
    CONSTRAINT furniture_embeddings_dimension_matches
        CHECK (vector_dims(embedding) = embedding_dimension),
    CONSTRAINT furniture_embeddings_text_hash_sha256
        CHECK (text_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_furniture_embeddings_item_model
    ON roompilot.furniture_embeddings(item_id, embedding_model);

CREATE OR REPLACE VIEW roompilot.furniture_embedding_source_current AS
WITH source_rows AS (
    SELECT
        item.item_id,
        btrim(concat_ws(
            '；',
            NULLIF(item.name_zh, ''),
            NULLIF(item.name_en, ''),
            NULLIF(item.category_name_zh, ''),
            NULLIF(item.normalized_type, ''),
            NULLIF(item.description, ''),
            NULLIF(array_to_string(item.rag_text, '；'), ''),
            NULLIF(array_to_string(item.features, '；'), ''),
            NULLIF(array_to_string(item.search_keywords, '；'), '')
        )) AS embedded_text,
        item.style_codes,
        item.updated_at,
        jsonb_strip_nulls(jsonb_build_object(
            'category', COALESCE(
                NULLIF(item.category_name_zh, ''),
                NULLIF(item.normalized_type, ''),
                NULLIF(item.category_code, '')
            ),
            'price_twd', item.price_twd,
            'width_cm', item.width_cm,
            'height_cm', item.height_cm,
            'role', item.role,
            'size_class', item.size_class,
            'style_primary', item.style_codes[1],
            'style_secondary', item.style_codes[2],
            'moods_flat', NULLIF(array_to_string(item.mood_tags, '|'), ''),
            'confidence', item.style_confidence
        )) || COALESCE(
            (
                SELECT jsonb_object_agg(
                    'room_' || lower(regexp_replace(room_code, '[^a-zA-Z0-9]+', '_', 'g')),
                    true
                )
                FROM unnest(item.room_codes) AS room_code
                WHERE btrim(room_code) <> ''
            ),
            '{}'::jsonb
        ) AS chroma_metadata
    FROM roompilot.furniture_catalog_current AS item
    WHERE item.is_active
)
SELECT
    source.item_id,
    NULL::bigint AS annotation_id,
    source.embedded_text,
    encode(digest(source.embedded_text, 'sha256'), 'hex') AS text_hash,
    'roompilot.catalog.rag.v1'::text AS text_format_version,
    source.style_codes[1] AS style_primary,
    source.style_codes[2] AS style_secondary,
    source.updated_at,
    source.chroma_metadata
FROM source_rows AS source
WHERE source.embedded_text <> '';

COMMENT ON TABLE roompilot.furniture_embeddings IS
'Operator-generated vectors for the licensed full-profile catalog; no vectors are bundled in Git.';

COMMENT ON VIEW roompilot.furniture_embedding_source_current IS
'Stable RAG text/hash/metadata derived from the active, license-documented public full-profile catalog.';

CREATE OR REPLACE FUNCTION roompilot.search_furniture_embeddings(
    query_embedding vector,
    query_model varchar,
    match_count integer DEFAULT 20
)
RETURNS TABLE (
    item_id text,
    annotation_id bigint,
    embedded_text text,
    cosine_distance double precision,
    cosine_similarity double precision
)
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $function$
    SELECT
        embedding.item_id,
        source.annotation_id,
        embedding.embedded_text,
        embedding.embedding <=> query_embedding AS cosine_distance,
        1.0 - (embedding.embedding <=> query_embedding) AS cosine_similarity
    FROM roompilot.furniture_embeddings AS embedding
    INNER JOIN roompilot.furniture_embedding_source_current AS source
        ON source.item_id = embedding.item_id
       AND source.text_hash = embedding.text_hash
    WHERE embedding.embedding_model = query_model
      AND vector_dims(embedding.embedding) = vector_dims(query_embedding)
    ORDER BY embedding.embedding <=> query_embedding, embedding.item_id
    LIMIT LEAST(GREATEST(match_count, 1), 100)
$function$;

CREATE OR REPLACE FUNCTION roompilot.search_furniture_embeddings_filtered(
    query_embedding vector,
    query_model varchar,
    match_count integer DEFAULT 50,
    room_type varchar DEFAULT NULL,
    category_values text[] DEFAULT NULL,
    price_min integer DEFAULT NULL,
    price_max integer DEFAULT NULL,
    max_width_cm numeric DEFAULT NULL,
    max_height_cm numeric DEFAULT NULL,
    item_role varchar DEFAULT NULL,
    item_size_class varchar DEFAULT NULL
)
RETURNS TABLE (
    item_id text,
    annotation_id bigint,
    embedded_text text,
    metadata jsonb,
    cosine_distance double precision,
    cosine_similarity double precision
)
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $function$
    SELECT
        embedding.item_id,
        source.annotation_id,
        embedding.embedded_text,
        source.chroma_metadata AS metadata,
        embedding.embedding <=> query_embedding AS cosine_distance,
        1.0 - (embedding.embedding <=> query_embedding) AS cosine_similarity
    FROM roompilot.furniture_embeddings AS embedding
    INNER JOIN roompilot.furniture_embedding_source_current AS source
        ON source.item_id = embedding.item_id
       AND source.text_hash = embedding.text_hash
    WHERE embedding.embedding_model = query_model
      AND vector_dims(embedding.embedding) = vector_dims(query_embedding)
      AND jsonb_typeof(source.chroma_metadata) = 'object'
      AND (
          room_type IS NULL
          OR COALESCE((source.chroma_metadata ->> ('room_' || room_type))::boolean, false)
      )
      AND (
          category_values IS NULL
          OR source.chroma_metadata ->> 'category' = ANY(category_values)
      )
      AND (
          price_min IS NULL
          OR NULLIF(source.chroma_metadata ->> 'price_twd', '')::numeric >= price_min
      )
      AND (
          price_max IS NULL
          OR NULLIF(source.chroma_metadata ->> 'price_twd', '')::numeric <= price_max
      )
      AND (
          max_width_cm IS NULL
          OR NULLIF(source.chroma_metadata ->> 'width_cm', '')::numeric <= max_width_cm
      )
      AND (
          max_height_cm IS NULL
          OR NULLIF(source.chroma_metadata ->> 'height_cm', '')::numeric <= max_height_cm
      )
      AND (
          item_role IS NULL
          OR source.chroma_metadata ->> 'role' = item_role
      )
      AND (
          item_size_class IS NULL
          OR source.chroma_metadata ->> 'size_class' = item_size_class
      )
    ORDER BY embedding.embedding <=> query_embedding, embedding.item_id
    LIMIT LEAST(GREATEST(match_count, 1), 100)
$function$;
