CREATE TABLE IF NOT EXISTS marketing_campaigns (
  campaign_id SERIAL PRIMARY KEY,
  campaign_name VARCHAR(200) NOT NULL,
  campaign_type VARCHAR(50) NOT NULL,
  channel VARCHAR(50) NOT NULL,
  budget NUMERIC(12, 2) NOT NULL,
  currency CHAR(3) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  target_audience JSONB,
  status VARCHAR(20) NOT NULL,
  created_by VARCHAR(100),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_status ON marketing_campaigns (status);
CREATE INDEX IF NOT EXISTS idx_campaigns_dates ON marketing_campaigns (start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_campaigns_type ON marketing_campaigns (campaign_type);

CREATE TABLE IF NOT EXISTS seo_keywords (
  keyword_id SERIAL PRIMARY KEY,
  keyword VARCHAR(255) UNIQUE NOT NULL,
  keyword_category VARCHAR(100),
  target_url VARCHAR(500),
  search_volume INT,
  competition_score NUMERIC(3, 2),
  cpc_estimate NUMERIC(8, 2),
  currency CHAR(3) DEFAULT 'USD',
  current_rank INT,
  target_rank INT,
  is_tracked BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_keywords_category ON seo_keywords (keyword_category);
CREATE INDEX IF NOT EXISTS idx_keywords_rank ON seo_keywords (current_rank);

CREATE TABLE IF NOT EXISTS feature_flags (
  flag_id SERIAL PRIMARY KEY,
  flag_key VARCHAR(100) UNIQUE NOT NULL,
  flag_name VARCHAR(200) NOT NULL,
  description TEXT,
  is_enabled BOOLEAN DEFAULT FALSE,
  rollout_percentage INT DEFAULT 0 CHECK (rollout_percentage >= 0 AND rollout_percentage <= 100),
  targeting_rules JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employees (
  employee_id SERIAL PRIMARY KEY,
  employee_number VARCHAR(20) UNIQUE NOT NULL,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  department VARCHAR(100) NOT NULL,
  job_title VARCHAR(150) NOT NULL,
  level VARCHAR(20),
  manager_id INT REFERENCES employees (employee_id),
  hire_date DATE NOT NULL,
  termination_date DATE,
  employment_status VARCHAR(20) DEFAULT 'ACTIVE',
  location VARCHAR(100),
  remote_status VARCHAR(20),
  salary NUMERIC(12, 2),
  currency CHAR(3),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employees_department ON employees (department);
CREATE INDEX IF NOT EXISTS idx_employees_manager ON employees (manager_id);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees (employment_status);

CREATE TABLE IF NOT EXISTS general_ledger (
  entry_id BIGSERIAL PRIMARY KEY,
  entry_date DATE NOT NULL,
  entry_number VARCHAR(50) UNIQUE NOT NULL,
  account_code VARCHAR(20) NOT NULL,
  account_name VARCHAR(200) NOT NULL,
  account_type VARCHAR(50) NOT NULL,
  debit_amount NUMERIC(15, 2) DEFAULT 0.00,
  credit_amount NUMERIC(15, 2) DEFAULT 0.00,
  currency CHAR(3) NOT NULL,
  transaction_type VARCHAR(100),
  reference_id BIGINT,
  reference_type VARCHAR(50),
  description TEXT,
  posted_by VARCHAR(100),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gl_date ON general_ledger (entry_date);
CREATE INDEX IF NOT EXISTS idx_gl_account ON general_ledger (account_code);
CREATE INDEX IF NOT EXISTS idx_gl_type ON general_ledger (transaction_type);
