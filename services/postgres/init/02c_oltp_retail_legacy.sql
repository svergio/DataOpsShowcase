-- Retail lineage: canonical marketplace keys + nullable legacy overlays (migration-era DWH style).
COMMENT ON SCHEMA public IS 'OLTP augmented with optional legacy-era duplicate keys alongside normalized FKs.';

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS legacy_crm_customer_id VARCHAR(96);

COMMENT ON COLUMN users.legacy_crm_customer_id IS 'Optional string key from imported CRM (~30% intentionally NULL — broken backfill simulator).';

ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(64),
  ADD COLUMN IF NOT EXISTS campaign_id INTEGER,
  ADD COLUMN IF NOT EXISTS legacy_campaign_code VARCHAR(96),
  ADD COLUMN IF NOT EXISTS legacy_order_ref VARCHAR(128),
  ADD COLUMN IF NOT EXISTS subtotal_before_discount NUMERIC(12, 2),
  ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS order_lineage VARCHAR(24) NOT NULL DEFAULT 'canonical';

COMMENT ON COLUMN orders.coupon_code IS 'Promotion code surfaced at checkout.';
COMMENT ON COLUMN orders.campaign_id IS 'Soft pointer to marketing_campaigns.campaign_id (no FK — legacy ingestion and partial backfills).';
COMMENT ON COLUMN orders.legacy_campaign_code IS 'Orphan textual campaign slug from legacy storefront (often no FK).';
COMMENT ON COLUMN orders.legacy_order_ref IS 'Duplicate business key exported from ERP/POS ingest.';
COMMENT ON COLUMN orders.order_lineage IS 'canonical — consistent joins; legacy_stub — FKs may be intentionally NULL.';

