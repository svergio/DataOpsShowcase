CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS vault;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.pipeline_watermarks (
  pipeline_name TEXT PRIMARY KEY,
  watermark_value TEXT NOT NULL,
  last_run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  records_processed BIGINT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
  run_id BIGSERIAL PRIMARY KEY,
  dag_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  source TEXT,
  layer TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running',
  rows_in BIGINT,
  rows_out BIGINT,
  rows_quarantined BIGINT,
  error_message TEXT,
  payload JSONB
);

CREATE TABLE IF NOT EXISTS meta.dq_results (
  id BIGSERIAL PRIMARY KEY,
  dag_id TEXT NOT NULL,
  check_name TEXT NOT NULL,
  table_name TEXT NOT NULL,
  severity TEXT NOT NULL,
  passed BOOLEAN NOT NULL,
  observed_value TEXT,
  expected_value TEXT,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  details JSONB
);

CREATE TABLE IF NOT EXISTS raw.kafka_orders (
  ingest_uuid UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  topic TEXT NOT NULL,
  partition_id INT,
  kafka_offset BIGINT,
  event_id TEXT,
  event_type TEXT,
  order_id BIGINT,
  customer_id BIGINT,
  total_amount NUMERIC(14, 2),
  currency CHAR(3),
  country_code CHAR(2),
  payload JSONB NOT NULL,
  event_ts TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_kafka_orders_event_id ON raw.kafka_orders(event_id);
CREATE INDEX IF NOT EXISTS idx_raw_kafka_orders_order_id ON raw.kafka_orders(order_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_kafka_orders_tpo
  ON raw.kafka_orders(topic, partition_id, kafka_offset);

CREATE TABLE IF NOT EXISTS raw.kafka_payments (
  ingest_uuid UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  topic TEXT NOT NULL,
  partition_id INT,
  kafka_offset BIGINT,
  event_id TEXT,
  event_type TEXT,
  payment_id BIGINT,
  order_id BIGINT,
  transaction_id TEXT,
  amount NUMERIC(14, 2),
  currency CHAR(3),
  payment_method TEXT,
  status TEXT,
  decline_reason TEXT,
  payload JSONB NOT NULL,
  event_ts TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_kafka_payments_event_id ON raw.kafka_payments(event_id);
CREATE INDEX IF NOT EXISTS idx_raw_kafka_payments_order_id ON raw.kafka_payments(order_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_kafka_payments_tpo
  ON raw.kafka_payments(topic, partition_id, kafka_offset);

CREATE TABLE IF NOT EXISTS raw.minio_files_landing (
  file_path TEXT PRIMARY KEY,
  prefix TEXT NOT NULL,
  bucket TEXT NOT NULL,
  size_bytes BIGINT,
  etag TEXT,
  status TEXT NOT NULL DEFAULT 'discovered',
  rows_loaded BIGINT,
  loaded_at TIMESTAMPTZ,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  payload JSONB
);

CREATE TABLE IF NOT EXISTS raw.oltp_users (
  user_id BIGINT,
  email TEXT,
  full_name TEXT,
  created_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (user_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS raw.oltp_sellers (
  seller_id BIGINT,
  seller_name TEXT,
  rating NUMERIC(3, 2),
  created_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (seller_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS raw.oltp_products (
  product_id BIGINT,
  seller_id BIGINT,
  sku TEXT,
  product_name TEXT,
  category TEXT,
  price NUMERIC(12, 2),
  is_active BOOLEAN,
  created_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (product_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS raw.oltp_orders (
  order_id BIGINT,
  user_id BIGINT,
  order_ts TIMESTAMPTZ,
  status TEXT,
  currency_code CHAR(3),
  total_amount NUMERIC(12, 2),
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (order_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS raw.oltp_order_items (
  order_item_id BIGINT,
  order_id BIGINT,
  product_id BIGINT,
  quantity INT,
  unit_price NUMERIC(12, 2),
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (order_item_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS staging.stg_customers (
  customer_id BIGINT PRIMARY KEY,
  email TEXT NOT NULL,
  full_name TEXT NOT NULL,
  registered_at TIMESTAMPTZ,
  source_record_hash TEXT NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staging.stg_orders (
  order_id BIGINT PRIMARY KEY,
  customer_id BIGINT,
  order_ts TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  currency_code CHAR(3) NOT NULL,
  total_amount NUMERIC(14, 2) NOT NULL,
  source_record_hash TEXT NOT NULL,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staging.stg_order_events (
  event_uuid TEXT PRIMARY KEY,
  event_id TEXT,
  event_type TEXT,
  order_id BIGINT,
  customer_id BIGINT,
  total_amount NUMERIC(14, 2),
  currency CHAR(3),
  country_code CHAR(2),
  event_ts TIMESTAMPTZ,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staging.stg_payment_events (
  event_uuid TEXT PRIMARY KEY,
  event_id TEXT,
  event_type TEXT,
  payment_id BIGINT,
  order_id BIGINT,
  transaction_id TEXT,
  amount NUMERIC(14, 2),
  currency CHAR(3),
  payment_method TEXT,
  status TEXT,
  decline_reason TEXT,
  event_ts TIMESTAMPTZ,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staging.stg_minio_payments (
  event_uuid TEXT PRIMARY KEY,
  source_file TEXT NOT NULL,
  payment_id BIGINT,
  order_id BIGINT,
  amount NUMERIC(14, 2),
  currency CHAR(3),
  status TEXT,
  event_ts TIMESTAMPTZ,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vault.hub_customers (
  customer_hk CHAR(64) PRIMARY KEY,
  customer_bk TEXT NOT NULL UNIQUE,
  load_dts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  record_source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vault.hub_orders (
  order_hk CHAR(64) PRIMARY KEY,
  order_bk TEXT NOT NULL UNIQUE,
  load_dts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  record_source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vault.link_customer_orders (
  link_hk CHAR(64) PRIMARY KEY,
  customer_hk CHAR(64) NOT NULL REFERENCES vault.hub_customers(customer_hk),
  order_hk CHAR(64) NOT NULL REFERENCES vault.hub_orders(order_hk),
  load_dts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  record_source TEXT NOT NULL,
  UNIQUE(customer_hk, order_hk)
);

CREATE TABLE IF NOT EXISTS vault.sat_customer_details (
  customer_hk CHAR(64) NOT NULL REFERENCES vault.hub_customers(customer_hk),
  load_dts TIMESTAMPTZ NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL,
  effective_to TIMESTAMPTZ,
  is_current BOOLEAN NOT NULL DEFAULT TRUE,
  hash_diff CHAR(64) NOT NULL,
  email TEXT NOT NULL,
  full_name TEXT NOT NULL,
  record_source TEXT NOT NULL,
  PRIMARY KEY (customer_hk, load_dts)
);

CREATE INDEX IF NOT EXISTS idx_sat_customer_current
  ON vault.sat_customer_details(customer_hk) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS vault.sat_order_status (
  order_hk CHAR(64) NOT NULL REFERENCES vault.hub_orders(order_hk),
  load_dts TIMESTAMPTZ NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL,
  effective_to TIMESTAMPTZ,
  is_current BOOLEAN NOT NULL DEFAULT TRUE,
  hash_diff CHAR(64) NOT NULL,
  status TEXT NOT NULL,
  total_amount NUMERIC(14, 2) NOT NULL,
  currency CHAR(3) NOT NULL,
  record_source TEXT NOT NULL,
  PRIMARY KEY (order_hk, load_dts)
);

CREATE INDEX IF NOT EXISTS idx_sat_order_status_current
  ON vault.sat_order_status(order_hk) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS marts.dim_customers (
  customer_hk CHAR(64) PRIMARY KEY,
  customer_bk TEXT NOT NULL,
  email TEXT NOT NULL,
  full_name TEXT NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL,
  effective_to TIMESTAMPTZ,
  is_current BOOLEAN NOT NULL,
  load_dts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS marts.fct_orders (
  order_hk CHAR(64) PRIMARY KEY,
  order_bk TEXT NOT NULL,
  customer_hk CHAR(64) NOT NULL,
  status TEXT NOT NULL,
  total_amount NUMERIC(14, 2) NOT NULL,
  currency CHAR(3) NOT NULL,
  order_ts TIMESTAMPTZ NOT NULL,
  load_dts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
