CREATE SCHEMA IF NOT EXISTS dbt_rest;

CREATE TABLE IF NOT EXISTS dbt_rest.runs (
    run_id UUID PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    duration_sec DOUBLE PRECISION,
    job_name TEXT,
    web_target TEXT,
    logs TEXT,
    artifact_names JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS runs_status_created_idx ON dbt_rest.runs (status, created_at DESC);
