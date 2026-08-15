CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS roompilot;

CREATE TABLE IF NOT EXISTS roompilot.furniture_catalog (
    item_id text PRIMARY KEY,
    kind text NOT NULL DEFAULT 'furniture',
    name_en text NOT NULL,
    name_zh text,
    category_code text,
    category_name_zh text,
    source_type text,
    normalized_type text,
    taxonomy_group text,
    taxonomy_group_zh text,
    taxonomy_type_zh text,
    catalog_scope text NOT NULL DEFAULT 'developer_supplied',
    role text,
    width_cm double precision NOT NULL CHECK (width_cm > 0),
    depth_cm double precision NOT NULL CHECK (depth_cm > 0),
    height_cm double precision NOT NULL CHECK (height_cm > 0),
    primary_color text,
    primary_material text,
    style_codes text[] NOT NULL DEFAULT '{}',
    style_confidences double precision[] NOT NULL DEFAULT '{}',
    style_confidence double precision,
    style_assignment_source text,
    room_codes text[] NOT NULL DEFAULT '{}',
    description text,
    rag_text text[] NOT NULL DEFAULT '{}',
    mood_tags text[] NOT NULL DEFAULT '{}',
    features text[] NOT NULL DEFAULT '{}',
    search_keywords text[] NOT NULL DEFAULT '{}',
    object_type_zh text,
    visual_weight text,
    height_zone text,
    size_class text,
    pattern text,
    must_against_wall boolean NOT NULL DEFAULT false,
    can_rotate boolean NOT NULL DEFAULT true,
    usable_for_moodboard boolean NOT NULL DEFAULT true,
    glb_url text,
    front_image_url text,
    side_image_url text,
    angle_45_image_url text,
    price_twd integer,
    is_active boolean NOT NULL DEFAULT true,
    source_license text NOT NULL,
    source_url text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW roompilot.furniture_catalog_current AS
SELECT * FROM roompilot.furniture_catalog WHERE is_active;

COMMENT ON TABLE roompilot.furniture_catalog IS
'Developer-supplied, license-documented catalog for RoomPilot full profile.';
