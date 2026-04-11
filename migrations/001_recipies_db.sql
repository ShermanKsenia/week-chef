-- Recipes catalog (table name per project convention)
CREATE TABLE IF NOT EXISTS recipies_db (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    text TEXT,
    type_kitchen TEXT,
    link TEXT,
    label TEXT,
    time_cook INTEGER,
    ingredients JSONB NOT NULL DEFAULT '[]'::jsonb,
    energy JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_recipies_db_label ON recipies_db (label);
CREATE INDEX IF NOT EXISTS idx_recipies_db_time_cook ON recipies_db (time_cook);
