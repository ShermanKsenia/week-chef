-- User profile JSON keyed by app user id (e.g. tg:<telegram_user_id>)
CREATE TABLE IF NOT EXISTS weekchef_profiles (
    user_key TEXT PRIMARY KEY,
    profile_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
