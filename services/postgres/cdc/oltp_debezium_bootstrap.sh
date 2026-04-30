#!/bin/sh
set -eu

DB="${POSTGRES_DB:-postgres}"
PASSWORD="${DEBEZIUM_OLTP_PASSWORD:-debezium_oltp_pass}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'debezium_oltp') THEN
    CREATE ROLE debezium_oltp WITH REPLICATION LOGIN PASSWORD '${PASSWORD}';
  END IF;
END
\$\$;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${DB}" <<-EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication WHERE pubname = 'dbz_publication_oltp'
  ) THEN
    CREATE PUBLICATION dbz_publication_oltp FOR ALL TABLES;
  END IF;
END
\$\$;
GRANT USAGE ON SCHEMA public TO debezium_oltp;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium_oltp;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium_oltp;
EOSQL
