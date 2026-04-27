-- Migration: enforce DB-level idempotency for Kafka raw landing tables.
-- Safe to re-run: uses IF NOT EXISTS / DEDUP cleanup before unique index creation.
-- Apply against postgres_olap (techmart_dwh).

BEGIN;

-- Deduplicate any pre-existing rows that violate (topic, partition_id, kafka_offset)
WITH ranked AS (
    SELECT ingest_uuid,
           ROW_NUMBER() OVER (
               PARTITION BY topic, partition_id, kafka_offset
               ORDER BY ingested_at DESC, ingest_uuid
           ) AS rn
    FROM raw.kafka_orders
    WHERE topic IS NOT NULL AND partition_id IS NOT NULL AND kafka_offset IS NOT NULL
)
DELETE FROM raw.kafka_orders k USING ranked r
 WHERE k.ingest_uuid = r.ingest_uuid AND r.rn > 1;

WITH ranked AS (
    SELECT ingest_uuid,
           ROW_NUMBER() OVER (
               PARTITION BY topic, partition_id, kafka_offset
               ORDER BY ingested_at DESC, ingest_uuid
           ) AS rn
    FROM raw.kafka_payments
    WHERE topic IS NOT NULL AND partition_id IS NOT NULL AND kafka_offset IS NOT NULL
)
DELETE FROM raw.kafka_payments k USING ranked r
 WHERE k.ingest_uuid = r.ingest_uuid AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_kafka_orders_tpo
  ON raw.kafka_orders(topic, partition_id, kafka_offset);

CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_kafka_payments_tpo
  ON raw.kafka_payments(topic, partition_id, kafka_offset);

COMMIT;
