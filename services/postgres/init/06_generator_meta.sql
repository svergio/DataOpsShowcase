CREATE SCHEMA IF NOT EXISTS generator;

CREATE TABLE IF NOT EXISTS generator.config_overrides (
    profile TEXT PRIMARY KEY,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO generator.config_overrides (profile, settings)
VALUES ('default', '{}'::jsonb)
ON CONFLICT (profile) DO NOTHING;
