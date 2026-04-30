-- Idempotent DDL for generator extensions (OLAP). On existing DB without this file, run once against DWH.
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
