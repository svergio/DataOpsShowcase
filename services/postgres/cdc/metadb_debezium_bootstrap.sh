#!/bin/sh
set -eu

PASSWORD="${DEBEZIUM_META_PASSWORD:-debezium_meta_pass}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'debezium_meta') THEN
    CREATE ROLE debezium_meta WITH REPLICATION LOGIN PASSWORD '${PASSWORD}';
  END IF;
END
\$\$;
EOSQL

for DB_NAME in airflow superset mlflow; do
  if ! psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" postgres -Atc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -qx 1; then
    continue
  fi
  PUBNAME="dbz_pub_${DB_NAME}"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" -c "CREATE PUBLICATION ${PUBNAME} FOR ALL TABLES;" 2>/dev/null || true

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
GRANT USAGE ON SCHEMA public TO debezium_meta;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium_meta;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium_meta;
EOSQL

done
