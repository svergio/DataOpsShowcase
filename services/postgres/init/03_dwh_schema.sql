CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE TABLE IF NOT EXISTS raw.orders_raw (
  order_id BIGINT,
  user_id BIGINT,
  order_ts TIMESTAMPTZ,
  status TEXT,
  currency_code CHAR(3),
  total_amount NUMERIC(12, 2),
  _ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.events_raw (
  event_id TEXT,
  user_id BIGINT,
  event_type TEXT,
  event_ts TIMESTAMPTZ,
  payload JSONB,
  _ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
