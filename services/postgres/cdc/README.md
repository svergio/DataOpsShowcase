# Logical replication bootstrap (Debezium)

Bootstrap scripts (`99_debezium_bootstrap.sh`) run **only during first Postgres init** (empty Docker volume).

## Existing deployments (volume already populated)

Apply manually as superuser (example OLTP):

1. Restart Postgres with `-c wal_level=logical -c max_replication_slots=16 -c max_wal_senders=10` (already in compose `command`).
2. Run SQL equivalent from `services/postgres/cdc/*_bootstrap.sh`, or truncate volume (data loss).

## Passwords

Override with `DEBEZIUM_OLTP_PASSWORD`, `DEBEZIUM_OLAP_PASSWORD`, `DEBEZIUM_META_PASSWORD` — must match `configs/debezium/*.json`.

## CDC vs dbt writes on OLAP

Use separate staging schemas (`cdc_*`) or consumers that do not conflict with nightly dbt models; see [`docs/ARCHITECTURE_CDC.md`](../../docs/ARCHITECTURE_CDC.md).
