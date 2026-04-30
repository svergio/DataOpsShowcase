# Apache Superset (OLAP dashboards)

Superset использует два подключения к PostgreSQL:

| Назначение | Хост Compose | База данных | Переменные |
|------------|----------------|-------------|------------|
| Метаданные Superset (чарты, дашборды, пользователи) | `postgres_metadb` | `SUPERSET_DB_NAME` (по умолчанию `superset`) | `SQLALCHEMY_DATABASE_URI`, `PG_META_*` из `.env` |
| DWH OLAP для датасетов | `postgres_olap` | `PG_OLAP_DB` (`techmart_dwh`) | `SUPERSET_DWH_DATABASE_URI` или сборка через `SUPERSET_DWH_*` / `PG_OLAP_*` |

Витрины для BI задаются моделями dbt в схеме **`dwh_marts`**. Обзор слоёв см. [diagrams/dwh-schemas.md](diagrams/dwh-schemas.md) и пайплайн [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md).

## Образ и драйвер

Контекст сборки — [services/superset/Dockerfile](services/superset/Dockerfile): базовый `apache/superset` + **`psycopg2-binary`** в venv (нужно для PostgreSQL URIs).

## Запуск

```bash
docker compose build superset_init
docker compose up -d postgres_metadb postgres_olap superset_init superset
```

Инициализация выполняет `superset db upgrade`, создаёт admin, `superset init`, затем [configs/app/superset_bootstrap.py](configs/app/superset_bootstrap.py): регистрируется подключение **TechMart DWH**, физические датасеты пяти март-таблиц и при наличии данных дашборд **`techmart-olap-overview`**.

## URLs

| Способ | URL |
|--------|-----|
| Рекомендуется (единый вход) | `http://localhost:${INGRESS_PORT:-8090}/superset/` |

Отдельного проброса `SUPERSET_PORT` на хост для UI нет. Логин: `SUPERSET_ADMIN_USER` / `SUPERSET_ADMIN_PASSWORD`.

## Примечания

- Первое развёртывание должно пробежать пайплайны и **dbt** по слою marts; иначе bootstrap пропускает недоступные таблицы.
- Метаданные на PostgreSQL заменили SQLite для стека; том `superset_home` сохранён для локальных файлов Superset при необходимости.
- При неверных ссылках во встроенном UI задайте корректный `SUPERSET_WEBSERVER_BASE_URL`/`APPLICATION_ROOT` под ваш образ Superset.
