# DataHub Migration Design (Dual Run)

## Goal
Постепенно заменить текущий Atlas-centric metadata flow на DataHub без остановки витрин и без смены контрактов в одном релизе.

## Current State
- Atlas поднимается как часть базового `docker-compose.yml`.
- dbt/Airflow lineage и схемы живут в PostgreSQL + артефактах dbt.
- Метаданные частично документируются вручную в `docs/`.

## Target State
- DataHub работает как второй каталог (`--profile datahub`) параллельно Atlas.
- Ingestion recipes в `infrastructure/datahub/ingestion/recipes/` запускаются по расписанию или вручную.
- Потребители переводятся на DataHub постепенно (UI/API), Atlas оставляется как fallback на период dual-run.

## Dual-Run Plan
1. **Bootstrap phase**
   - Поднять DataHub профиль.
   - Создать БД `datahub` в `postgres_metadb` (однократно).
   - Запустить первичную инъекцию metadata из PostgreSQL, Airflow, dbt.
2. **Validation phase**
   - Сравнить покрытие сущностей Atlas vs DataHub (таблицы, DAG, модели dbt).
   - Провалидировать ownership/tags/lineage для критичных витрин.
3. **Consumer migration**
   - Обновить внутренние runbook/документацию на ссылки DataHub.
   - Перевести команды на DataHub UI для поиска lineage.
4. **Exit criteria**
   - 2 спринта без регрессий.
   - Нет блокеров в DataHub ingest pipeline.
   - Atlas остается только как read-only fallback.

## Rollback
- Остановить профиль DataHub: `docker compose -f docker-compose.yml -f infrastructure/datahub/docker-compose.datahub.yml --profile datahub down`
- Вернуться к Atlas workflows (без миграции схем/данных в OLAP).
- Разобрать ошибки ingest и повторить dual-run без влияния на core DWH.
