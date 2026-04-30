#!/bin/sh
set -eu

DB="${POSTGRES_DB:-postgres}"
PASSWORD="${DEBEZIUM_OLAP_PASSWORD:-debezium_olap_pass}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'debezium_olap') THEN
    CREATE ROLE debezium_olap WITH REPLICATION LOGIN PASSWORD '${PASSWORD}';
  END IF;
END
\$\$;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${DB}" <<-EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication WHERE pubname = 'dbz_publication_olap'
  ) THEN
    CREATE PUBLICATION dbz_publication_olap FOR ALL TABLES;
  END IF;
END
\$\$;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${DB}" <<-EOSQL
GRANT USAGE ON SCHEMA public TO debezium_olap;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium_olap;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium_olap;
EOSQL
