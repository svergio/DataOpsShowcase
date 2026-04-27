# ER-диаграммы TechMart Data Platform

В этой папке хранятся ER-диаграммы для трёх источников данных, заполняемых
сервисом `data_generator`.

| Источник | Mermaid | DBML |
|----------|---------|------|
| OLTP PostgreSQL (`postgres_oltp`) | [`oltp-er.md`](./oltp-er.md) | [`oltp-er.dbml`](./oltp-er.dbml) |
| MinIO bucket `techmart-data` | [`minio-er.md`](./minio-er.md) | [`minio-er.dbml`](./minio-er.dbml) |
| Kafka топики `techmart.*` | [`kafka-er.md`](./kafka-er.md) | [`kafka-er.dbml`](./kafka-er.dbml) |

## Как смотреть

- **Mermaid (`.md`)** — рендерится на GitHub и в большинстве IDE
  (включая VS Code/Cursor с расширениями). Откройте Markdown preview.
- **DBML (`.dbml`)** — открывайте на [dbdiagram.io](https://dbdiagram.io/) или
  через CLI `dbml-cli` (например `dbml2sql oltp-er.dbml`).

## Связь с генератором

`generators/generator.py` поддерживает идентичные имена сущностей
и совместимые поля. Имена Kafka-топиков и MinIO-префиксов задаются через
переменные `.env` и должны совпадать с диаграммами.
