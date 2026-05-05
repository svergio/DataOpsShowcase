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

-- Extension OLTP landing + Kafka extension.
-- Canonical init path for new postgres_olap volumes is 04_dwh_extensions.sql.
-- 06_dwh_raw_generators_extensions.sql is kept as an idempotent patch for legacy volumes.
CREATE TABLE IF NOT EXISTS raw.kafka_extension_events (
  ingest_uuid UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  topic TEXT NOT NULL,
  partition_id INT NOT NULL DEFAULT 0,
  kafka_offset BIGINT NOT NULL,
  domain_code TEXT NOT NULL,
  event_id TEXT,
  event_type TEXT,
  payload JSONB NOT NULL,
  event_ts TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_kafka_ext_event_id ON raw.kafka_extension_events(event_id);
CREATE INDEX IF NOT EXISTS idx_raw_kafka_ext_domain ON raw.kafka_extension_events(domain_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_kafka_ext_tpo
  ON raw.kafka_extension_events(topic, partition_id, kafka_offset);

CREATE TABLE IF NOT EXISTS raw.oltp_marketing_campaigns (
  campaign_id INT,
  campaign_name VARCHAR(200),
  campaign_type VARCHAR(50),
  channel VARCHAR(50),
  budget NUMERIC(12, 2),
  currency CHAR(3),
  start_date DATE,
  end_date DATE,
  target_audience JSONB,
  status VARCHAR(20),
  created_by VARCHAR(100),
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (campaign_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS raw.oltp_seo_keywords (
  keyword_id INT,
  keyword VARCHAR(255),
  keyword_category VARCHAR(100),
  target_url VARCHAR(500),
  search_volume INT,
  competition_score NUMERIC(3, 2),
  cpc_estimate NUMERIC(8, 2),
  currency CHAR(3),
  current_rank INT,
  target_rank INT,
  is_tracked BOOLEAN,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (keyword_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS raw.oltp_feature_flags (
  flag_id INT,
  flag_key VARCHAR(100),
  flag_name VARCHAR(200),
  description TEXT,
  is_enabled BOOLEAN,
  rollout_percentage INT,
  targeting_rules JSONB,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (flag_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS raw.oltp_employees (
  employee_id INT,
  employee_number VARCHAR(20),
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  email VARCHAR(255),
  department VARCHAR(100),
  job_title VARCHAR(150),
  level VARCHAR(20),
  manager_id INT,
  hire_date DATE,
  termination_date DATE,
  employment_status VARCHAR(20),
  location VARCHAR(100),
  remote_status VARCHAR(20),
  salary NUMERIC(12, 2),
  currency CHAR(3),
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (employee_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS raw.oltp_general_ledger (
  entry_id BIGINT,
  entry_date DATE,
  entry_number VARCHAR(50),
  account_code VARCHAR(20),
  account_name VARCHAR(200),
  account_type VARCHAR(50),
  debit_amount NUMERIC(15, 2),
  credit_amount NUMERIC(15, 2),
  currency CHAR(3),
  transaction_type VARCHAR(100),
  reference_id BIGINT,
  reference_type VARCHAR(50),
  description TEXT,
  posted_by VARCHAR(100),
  created_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_run_id TEXT,
  PRIMARY KEY (entry_id, ingested_at)
);

CREATE TABLE IF NOT EXISTS staging.stg_customers (
  customer_id BIGINT PRIMARY KEY,
  customer_hash CHAR(64) NOT NULL,
  masked_email TEXT,
  masked_name TEXT,
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
  customer_hash CHAR(64) NOT NULL,
  masked_email TEXT,
  masked_name TEXT,
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
  customer_hash CHAR(64),
  masked_email TEXT,
  masked_name TEXT,
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
