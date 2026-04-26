# TechMart Data Platform Showcase

Pet-project data platform for a marketplace analytics use case.

## Project Goals

- Build end-to-end batch and streaming data pipelines
- Practice orchestration with Airflow
- Transform data with dbt and Spark
- Add data quality checks and monitoring
- Implement analytics marts and near-real-time processing

## Repository Structure

- `services` - service-level configs (Postgres, Airflow, Spark, Redis, etc.)
- `pipelines` - DAGs, custom operators, sensors, pipeline utils
- `spark_jobs` - PySpark jobs for ingestion and transformations
- `dbt` - dbt project models, macros, snapshots, tests
- `streaming` - Kafka producers/consumers and streaming helpers
- `data_generators` - synthetic data and JSON schemas
- `infra` - monitoring and infra-related assets
- `scripts` - setup, maintenance, deployment, testing helpers
- `configs` - shared app and tool configuration
- `docs` - architecture and documentation materials
- `docs/Tasks` - task breakdown extracted from `Task.md`
- `tests` - test-related directories for implementation stage

## Tasks

Task descriptions are available in:

- `Task.md` - source document
- `docs/Tasks` - separated task files (`Task_01...Task_50`)

## Quick Start

1. Clone the repository
2. Configure environment variables
3. Bring up local services with Docker Compose
4. Start implementing tasks sequentially from `docs/Tasks`
