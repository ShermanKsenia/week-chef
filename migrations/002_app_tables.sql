-- Application state (same database as recipes; separate tables)
CREATE TABLE IF NOT EXISTS weekchef_sessions (
    telegram_user_id BIGINT PRIMARY KEY,
    state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS weekchef_oauth_tokens (
    user_key TEXT PRIMARY KEY,
    token_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS weekchef_inventory (
    id BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    qty NUMERIC,
    unit TEXT,
    UNIQUE (user_key, name_normalized)
);
