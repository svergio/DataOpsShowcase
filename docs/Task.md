# 🚀 Data Platform Pet-Project: E-Commerce Analytics Platform

## 📊 Бизнес-кейс: Marketplace "TechMart"

**Описание**: Интернет-магазин электроники и гаджетов с несколькими продавцами (marketplace model). Нужна аналитическая платформа для:
- Анализа продаж в реальном времени
- Рекомендательной системы
- Fraud detection
- Inventory management
- Seller performance analytics

**Источники данных**:
- OLTP база (PostgreSQL) - orders, users, products, sellers
- Event stream - user clickstream, cart events, search queries
- External API - курсы валют, shipment tracking
- CSV files - product catalog updates от sellers

---

## 🏗️ Архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
├─────────────────┬──────────────┬────────────┬───────────────────┤
│  PostgreSQL     │   API Mock   │  Kafka/    │   CSV Files       │
│  (OLTP)         │   (External) │  Redis     │   (S3/MinIO)      │
│  - orders       │   - currency │  Stream    │   - catalog       │
│  - users        │   - shipping │  - clicks  │   - inventory     │
│  - products     │              │  - events  │                   │
└────────┬────────┴──────┬───────┴─────┬──────┴─────┬─────────────┘
         │               │             │            │
         ▼               ▼             ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER                             │
├─────────────────┬──────────────┬────────────┬───────────────────┤
│  Airflow DAGs   │   Spark      │  Kafka     │   Python          │
│  (batch)        │   Streaming  │  Consumer  │   Scripts         │
└────────┬────────┴──────┬───────┴─────┬──────┴─────┬─────────────┘
         │               │             │            │
         ▼               ▼             ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                               │
├──────────────────────────┬──────────────────────────────────────┤
│  Raw Zone (S3/MinIO)     │   HDFS (Parquet)                     │
│  - landing/              │   - /raw/                            │
│  - archive/              │   - /processed/                      │
├──────────────────────────┴──────────────────────────────────────┤
│  PostgreSQL (DWH)        │   Redis (Cache/State)                │
│  - raw schema            │   - session data                     │
│  - staging schema        │   - aggregations                     │
│  - marts schema          │                                       │
└────────┬─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TRANSFORMATION LAYER                           │
├─────────────────┬───────────────────────────────────────────────┤
│  dbt (SQL)      │   Spark Jobs (PySpark)                        │
│  - staging      │   - complex aggregations                      │
│  - intermediate │   - ML features                               │
│  - marts        │   - deduplication                             │
└────────┬────────┴───────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVING LAYER                               │
├─────────────────┬──────────────┬────────────────────────────────┤
│  PostgreSQL     │   Redis      │   API Layer                    │
│  (marts)        │   (cache)    │   (FastAPI - optional)         │
└─────────────────┴──────────────┴────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ORCHESTRATION & MONITORING                       │
├─────────────────┬──────────────┬────────────────────────────────┤
│  Airflow        │   Prometheus │   Custom Dashboard             │
│  - DAG runs     │   + Grafana  │   (Streamlit/Dash)             │
│  - scheduling   │              │                                │
└─────────────────┴──────────────┴────────────────────────────────┘
```

---

## 📁 Структура монорепозитория

```
techmart-data-platform/
│
├── README.md
├── docker-compose.yml
├── .env.example
├── Makefile
│
├── services/                          # Сервисы и приложения
│   ├── postgres/
│   │   ├── init/
│   │   │   ├── 01_create_databases.sql
│   │   │   ├── 02_oltp_schema.sql
│   │   │   └── 03_dwh_schema.sql
│   │   └── Dockerfile
│   ├── airflow/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── config/
│   │       └── airflow.cfg
│   ├── spark/
│   │   ├── Dockerfile
│   │   └── conf/
│   │       └── spark-defaults.conf
│   ├── kafka/
│   │   └── docker-compose.kafka.yml
│   ├── minio/
│   │   └── config/
│   └── redis/
│       └── redis.conf
│
├── pipelines/                         # Airflow DAGs и пайплайны
│   ├── dags/
│   │   ├── __init__.py
│   │   ├── ingestion/
│   │   │   ├── ingest_oltp_daily.py
│   │   │   ├── ingest_api_currency.py
│   │   │   ├── ingest_catalog_files.py
│   │   │   └── stream_events_batch.py
│   │   ├── transformation/
│   │   │   ├── run_dbt_staging.py
│   │   │   ├── run_dbt_marts.py
│   │   │   └── spark_aggregations.py
│   │   ├── quality/
│   │   │   ├── data_quality_checks.py
│   │   │   └── schema_validation.py
│   │   └── maintenance/
│   │       ├── cleanup_old_data.py
│   │       └── backfill_orchestrator.py
│   ├── plugins/
│   │   ├── operators/
│   │   │   ├── spark_operator.py
│   │   │   └── dbt_operator.py
│   │   └── sensors/
│   │       └── s3_sensor.py
│   └── utils/
│       ├── db_helpers.py
│       ├── s3_helpers.py
│       └── notification.py
│
├── spark_jobs/                        # PySpark приложения
│   ├── __init__.py
│   ├── ingestion/
│   │   ├── oltp_to_raw.py
│   │   └── kafka_consumer.py
│   ├── transformation/
│   │   ├── orders_aggregation.py
│   │   ├── user_segmentation.py
│   │   ├── product_recommendations.py
│   │   └── fraud_detection.py
│   ├── optimization/
│   │   ├── partition_optimizer.py
│   │   └── compaction_job.py
│   ├── utils/
│   │   ├── spark_config.py
│   │   └── data_quality.py
│   └── tests/
│       └── test_transformations.py
│
├── dbt/                               # dbt проект
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── packages.yml
│   ├── models/
│   │   ├── staging/
│   │   │   ├── _staging.yml
│   │   │   ├── stg_orders.sql
│   │   │   ├── stg_users.sql
│   │   │   ├── stg_products.sql
│   │   │   ├── stg_sellers.sql
│   │   │   └── stg_events.sql
│   │   ├── intermediate/
│   │   │   ├── _intermediate.yml
│   │   │   ├── int_orders_enriched.sql
│   │   │   ├── int_user_sessions.sql
│   │   │   └── int_product_metrics.sql
│   │   └── marts/
│   │       ├── core/
│   │       │   ├── _core.yml
│   │       │   ├── fct_orders.sql
│   │       │   ├── fct_events.sql
│   │       │   ├── dim_users.sql
│   │       │   ├── dim_products.sql
│   │       │   └── dim_sellers.sql
│   │       ├── analytics/
│   │       │   ├── _analytics.yml
│   │       │   ├── daily_sales_summary.sql
│   │       │   ├── seller_performance.sql
│   │       │   ├── product_funnel.sql
│   │       │   └── user_cohorts.sql
│   │       └── ml/
│   │           ├── user_features.sql
│   │           └── product_features.sql
│   ├── macros/
│   │   ├── generate_schema_name.sql
│   │   ├── test_not_null_where.sql
│   │   └── custom_tests.sql
│   ├── snapshots/
│   │   ├── product_prices_snapshot.sql
│   │   └── inventory_snapshot.sql
│   └── tests/
│       └── assert_positive_revenue.sql
│
├── streaming/                         # Streaming приложения
│   ├── producers/
│   │   ├── clickstream_producer.py
│   │   ├── event_simulator.py
│   │   └── cdc_producer.py
│   ├── consumers/
│   │   ├── redis_consumer.py
│   │   ├── realtime_aggregator.py
│   │   └── fraud_detector.py
│   └── utils/
│       └── kafka_helpers.py
│
├── data_generators/                   # Генераторы тестовых данных
│   ├── generate_oltp_data.py
│   ├── generate_events.py
│   ├── generate_catalog_files.py
│   └── schemas/
│       ├── orders_schema.json
│       └── events_schema.json
│
├── infra/                             # Инфраструктура как код
│   ├── terraform/ (optional)
│   ├── monitoring/
│   │   ├── prometheus.yml
│   │   ├── grafana/
│   │   │   └── dashboards/
│   │   │       ├── airflow_metrics.json
│   │   │       └── data_quality.json
│   │   └── alertmanager/
│   │       └── alerts.yml
│   └── docker/
│       ├── airflow.Dockerfile
│       ├── spark.Dockerfile
│       └── jupyter.Dockerfile
│
├── scripts/                           # Утилиты и скрипты
│   ├── setup/
│   │   ├── init_project.sh
│   │   ├── create_databases.sh
│   │   └── seed_data.sh
│   ├── maintenance/
│   │   ├── cleanup_logs.sh
│   │   ├── backup_postgres.sh
│   │   └── vacuum_tables.py
│   ├── deployment/
│   │   ├── deploy.sh
│   │   └── rollback.sh
│   └── testing/
│       └── run_integration_tests.sh
│
├── configs/                           # Конфигурационные файлы
│   ├── spark/
│   │   └── log4j.properties
│   ├── airflow/
│   │   └── connections.json
│   └── app/
│       ├── config.yaml
│       └── secrets.example.yaml
│
├── tests/                             # Тесты
│   ├── unit/
│   │   ├── test_dags.py
│   │   ├── test_spark_jobs.py
│   │   └── test_utils.py
│   ├── integration/
│   │   ├── test_pipelines.py
│   │   └── test_data_flow.py
│   └── fixtures/
│       └── sample_data/
│
├── docs/                              # Документация
│   ├── architecture.md
│   ├── setup.md
│   ├── data_dictionary.md
│   ├── runbook.md
│   └── diagrams/
│
├── notebooks/                         # Jupyter notebooks для анализа
│   ├── exploratory/
│   └── debugging/
│
├── requirements/                      # Python зависимости
│   ├── base.txt
│   ├── airflow.txt
│   ├── spark.txt
│   └── dev.txt
│
└── .github/                           # CI/CD
    └── workflows/
        ├── ci.yml
        ├── dbt_tests.yml
        └── deploy.yml
```

---

## 🧪 50+ Практических задач

### 🟢 BEGINNER (10 задач)

#### **Task 1: Настройка базового окружения**
- **Описание**: Создать docker-compose с Postgres, Airflow, MinIO
- **Цель**: Понимание инфраструктуры, Docker
- **Входные данные**: docker-compose.yml template
- **Результат**: Поднятое окружение, доступ к UI Airflow
- **Реализация**:
  1. Создать docker-compose.yml с сервисами
  2. Настроить volumes для персистентности
  3. Создать init скрипты для Postgres
  4. Добавить healthchecks

#### **Task 2: Генерация синтетических данных OLTP**
- **Описание**: Создать Python скрипт для генерации реалистичных данных orders, users, products
- **Цель**: Работа с Faker, понимание бизнес-логики
- **Входные данные**: Схема БД
- **Результат**: 100K orders, 10K users, 1K products в Postgres
- **Реализация**:
  1. Использовать Faker для генерации
  2. Соблюдать referential integrity
  3. Добавить временные паттерны (сезонность)
  4. Сохранить в OLTP БД

#### **Task 3: Простой Airflow DAG для extract**
- **Описание**: Создать DAG который читает данные из OLTP Postgres и сохраняет в S3 (MinIO) как CSV
- **Цель**: Базовый Airflow, S3 взаимодействие
- **Входные данные**: OLTP tables
- **Результат**: Файлы в S3: orders_YYYYMMDD.csv
- **Реализация**:
  1. Создать PostgresHook для чтения
  2. Использовать S3Hook для записи
  3. Добавить параметризацию по датам
  4. Настроить расписание (@daily)

#### **Task 4: Загрузка CSV файлов из S3 в Postgres**
- **Описание**: DAG который читает CSV из S3 и загружает в raw schema Postgres
- **Цель**: Reverse flow, bulk insert
- **Входные данные**: CSV в S3
- **Результат**: Таблица raw.orders_raw
- **Реализация**:
  1. S3Sensor для ожидания файла
  2. Pandas для чтения CSV
  3. SQLAlchemy bulk insert
  4. Логирование количества строк

#### **Task 5: Первая dbt модель - staging**
- **Описание**: Создать stg_orders.sql который очищает raw данные
- **Цель**: Базовый dbt, типизация данных
- **Входные данные**: raw.orders_raw
- **Результат**: staging.stg_orders с правильными типами
- **Реализация**:
  1. Инициализировать dbt проект
  2. Настроить profiles.yml
  3. Создать модель с CAST, COALESCE
  4. Добавить базовые тесты (not_null, unique)

#### **Task 6: Простой Spark job для подсчета**
- **Описание**: PySpark job который считает количество заказов по продавцам
- **Цель**: Базовый Spark, groupBy
- **Входные данные**: orders CSV в S3
- **Результат**: Агрегированный CSV в S3
- **Реализация**:
  1. SparkSession setup
  2. Чтение из S3
  3. groupBy + count
  4. Запись обратно в Parquet

#### **Task 7: Интеграция Spark job в Airflow**
- **Описание**: Создать DAG который запускает Spark job через SparkSubmitOperator
- **Цель**: Orchestration Spark jobs
- **Входные данные**: Spark job скрипт
- **Результат**: Автоматический запуск Spark job
- **Реализация**:
  1. Настроить Spark connection в Airflow
  2. Использовать SparkSubmitOperator
  3. Передать параметры через --conf
  4. Обработать успех/неудачу

#### **Task 8: Создание dimensions в dbt**
- **Описание**: Создать dim_users, dim_products из staging
- **Цель**: Dimensional modeling
- **Входные данные**: stg_users, stg_products
- **Результат**: Таблицы marts.dim_*
- **Реализация**:
  1. Добавить surrogate keys (dbt_utils.surrogate_key)
  2. Выбрать нужные атрибуты
  3. Добавить created_at, updated_at
  4. Тесты на уникальность

#### **Task 9: Fact table в dbt**
- **Описание**: Создать fct_orders с foreign keys на dimensions
- **Цель**: Star schema
- **Входные данные**: stg_orders + dimensions
- **Результат**: marts.fct_orders
- **Реализация**:
  1. JOIN staging с dimensions
  2. Выбрать measures (amount, quantity)
  3. Добавить grain (order_id)
  4. Relationships тесты

#### **Task 10: Базовый data quality check**
- **Описание**: DAG который проверяет количество записей, null values
- **Цель**: Data observability
- **Входные данные**: marts tables
- **Результат**: Алерт если checks failed
- **Реализация**:
  1. SQLCheckOperator в Airflow
  2. Queries для проверки
  3. Email alert при failure
  4. Логирование результатов

---

### 🟡 INTERMEDIATE (20 задач)

#### **Task 11: Инкрементальная загрузка в dbt**
- **Описание**: Переделать stg_orders на incremental materialization
- **Цель**: Оптимизация, работа с большими данными
- **Входные данные**: raw.orders_raw с updated_at
- **Результат**: Только новые/измененные записи
- **Реализация**:
  1. Использовать `{{ is_incremental() }}`
  2. Фильтрация по updated_at
  3. Стратегия merge/append
  4. Тестирование на историчности

#### **Task 12: Partitioning в Spark**
- **Описание**: Переписать Spark job с partitionBy по дате
- **Цель**: Оптимизация чтения/записи
- **Входные данные**: Orders dataset
- **Результат**: Partitioned Parquet в S3
- **Реализация**:
  1. Добавить partition column (order_date)
  2. partitionBy("year", "month", "day")
  3. Настроить coalesce для размера файлов
  4. Сравнить производительность

#### **Task 13: CDC с помощью dbt snapshots**
- **Описание**: Отслеживать изменения цен продуктов с помощью dbt snapshots
- **Цель**: SCD Type 2, история изменений
- **Входные данные**: products таблица
- **Результат**: snapshots.product_prices_snapshot
- **Реализация**:
  1. Создать snapshot с timestamp strategy
  2. Настроить updated_at column
  3. Запускать в DAG ежедневно
  4. Анализировать изменения

#### **Task 14: Data quality framework**
- **Описание**: Создать custom dbt tests для бизнес-правил
- **Цель**: Data contracts, quality assurance
- **Входные данные**: Бизнес-правила (order amount > 0)
- **Результат**: Кастомные тесты в macros/
- **Реализация**:
  1. Создать generic test в macros
  2. Параметризация теста
  3. Применить к моделям в .yml
  4. Интеграция в CI/CD

#### **Task 15: User segmentation в Spark**
- **Описание**: RFM анализ пользователей (Recency, Frequency, Monetary)
- **Цель**: Window functions, сложные аггрегации
- **Входные данные**: fct_orders
- **Результат**: user_segments таблица
- **Реализация**:
  1. Window functions для расчета метрик
  2. Квартили для сегментации
  3. UDF для scoring
  4. Запись в Postgres

#### **Task 16: Airflow XCom для передачи данных**
- **Описание**: Передавать метаданные между tasks через XCom
- **Цель**: Динамическая оркестрация
- **Входные данные**: Task outputs
- **Результат**: Следующий task получает параметры
- **Реализация**:
  1. xcom_push в первом task
  2. xcom_pull во втором
  3. Передача списка файлов для обработки
  4. Динамическое создание tasks

#### **Task 17: Join оптимизация в Spark**
- **Описание**: Оптимизировать join большой и малой таблицы
- **Цель**: Broadcast join, shuffle optimization
- **Входные данные**: Orders (большая) + Products (малая)
- **Результат**: Ускоренный join
- **Реализация**:
  1. Использовать broadcast() для малой таблицы
  2. Сравнить explain() до/после
  3. Настроить spark.sql.autoBroadcastJoinThreshold
  4. Измерить время выполнения

#### **Task 18: Intermediate слой в dbt**
- **Описание**: Создать int_orders_enriched с расширенной информацией
- **Цель**: Модульность, reusability
- **Входные данные**: stg_orders, dim_users, dim_products
- **Результат**: Enriched orders для нескольких marts
- **Реализация**:
  1. JOIN нескольких dimensions
  2. Добавить вычисляемые поля
  3. Использовать в нескольких marts
  4. Ephemeral vs table materialization

#### **Task 19: Daily sales summary mart**
- **Описание**: Агрегированная таблица продаж по дням
- **Цель**: Reporting marts, aggregations
- **Входные данные**: fct_orders
- **Результат**: marts.daily_sales_summary
- **Реализация**:
  1. GROUP BY date
  2. SUM, AVG, COUNT metrics
  3. Incremental materialization
  4. Pre-aggregation для BI

#### **Task 20: Late arriving data handling**
- **Описание**: Обработка заказов которые пришли с задержкой
- **Цель**: Idempotency, correctness
- **Входные данные**: Orders с разными created_at
- **Результат**: Корректные агрегации
- **Реализация**:
  1. Использовать updated_at вместо ingestion time
  2. Lookback window в incremental
  3. Merge strategy в dbt
  4. Тестирование на идемпотентность

#### **Task 21: Deduplication в Spark**
- **Описание**: Удалить дубликаты из event stream
- **Цель**: Data cleansing, window functions
- **Входные данные**: Raw events с дубликатами
- **Результат**: Deduplicated dataset
- **Реализация**:
  1. Window function с ROW_NUMBER
  2. Partition by unique key
  3. Order by timestamp DESC
  4. Filter where row_num = 1

#### **Task 22: Multi-source ingestion DAG**
- **Описание**: DAG который читает из API, CSV, и Postgres одновременно
- **Цель**: Orchestration, parallel execution
- **Входные данные**: Разные источники
- **Результат**: Данные в raw schema
- **Реализация**:
  1. Параллельные tasks для каждого источника
  2. Использовать task groups
  3. Downstream task для объединения
  4. Error handling для каждого источника

#### **Task 23: Schema validation**
- **Описание**: Валидация входящих данных против JSON schema
- **Цель**: Data contracts, early failure
- **Входные данные**: Raw CSV/JSON
- **Результат**: Rejection неправильных данных
- **Реализация**:
  1. Определить JSON schemas
  2. Python jsonschema library
  3. Quarantine для плохих данных
  4. Алерты при ошибках

#### **Task 24: Slowly Changing Dimension Type 2 в dbt**
- **Описание**: SCD2 для user addresses (историзация)
- **Цель**: Advanced dimensional modeling
- **Входные данные**: stg_user_addresses
- **Результат**: dim_user_addresses с valid_from/to
- **Реализация**:
  1. Использовать dbt snapshots или custom logic
  2. Добавить is_current flag
  3. valid_from, valid_to dates
  4. Surrogate key для версий

#### **Task 25: Product funnel analysis**
- **Описание**: Построить воронку: view → cart → purchase
- **Цель**: Funnel analysis, CTR расчеты
- **Входные данные**: events таблица
- **Результат**: marts.product_funnel
- **Реализация**:
  1. Window functions для упорядочивания событий
  2. CASE для определения стадий
  3. Конверсии между стадиями
  4. Group by product

#### **Task 26: Backfill automation**
- **Описание**: DAG для backfill исторических данных с параметрами
- **Цель**: Data recovery, reprocessing
- **Входные данные**: Date range parameters
- **Результат**: Заполненные данные за период
- **Реализация**:
  1. Параметризованный DAG (start_date, end_date)
  2. Идемпотентная логика
  3. Batching по дням/неделям
  4. Progress tracking

#### **Task 27: Data lineage documentation**
- **Описание**: Генерация дата-линейности с помощью dbt docs
- **Цель**: Documentation, governance
- **Входные данные**: dbt project
- **Результат**: dbt docs site
- **Реализация**:
  1. Добавить descriptions в .yml
  2. Генерировать dbt docs generate
  3. dbt docs serve для визуализации
  4. Интеграция в CI для автообновления

#### **Task 28: Caching в Redis для aggregations**
- **Описание**: Кешировать результаты тяжелых агрегаций в Redis
- **Цель**: Performance optimization, caching strategy
- **Входные данные**: Daily aggregations
- **Результат**: sub-second queries
- **Реализация**:
  1. После Spark job писать в Redis
  2. TTL для автоочистки
  3. Cache invalidation при новых данных
  4. Fallback к Postgres

#### **Task 29: Error handling и retries**
- **Описание**: Добавить retry logic и error notifications в DAG
- **Цель**: Resilience, observability
- **Входные данные**: Existing DAGs
- **Результат**: Self-healing pipelines
- **Реализация**:
  1. retries=3, retry_delay
  2. on_failure_callback для алертов
  3. Email/Slack notifications
  4. Dead letter queue для неудачных records

#### **Task 30: Dynamic DAG generation**
- **Описание**: Генерация DAGs из config файла для множества источников
- **Цель**: Масштабируемость, DRY
- **Входные данные**: YAML config с источниками
- **Результат**: Автоматически созданные DAGs
- **Реализация**:
  1. Читать config.yaml
  2. Loop для создания DAGs
  3. Template DAG с параметрами
  4. Регистрация в globals()

---

### 🔴 ADVANCED (20 задач)

#### **Task 31: Real-time streaming с Kafka**
- **Описание**: Настроить Kafka producer/consumer для clickstream
- **Цель**: Streaming architecture
- **Входные данные**: Симулированные клики
- **Результат**: Events в Kafka topics
- **Реализация**:
  1. Kafka producer для генерации событий
  2. Topic partitioning по user_id
  3. Consumer group для обработки
  4. At-least-once delivery

#### **Task 32: Spark Structured Streaming**
- **Описание**: Real-time aggregation событий с помощью Spark Streaming
- **Цель**: Streaming processing
- **Входные данные**: Kafka topic
- **Результат**: Realtime метрики в Redis
- **Реализация**:
  1. readStream from Kafka
  2. Window aggregations (tumbling, sliding)
  3. Watermarking для late data
  4. writeStream to Redis/Postgres

#### **Task 33: CDC с Debezium (имитация)**
- **Описание**: Симулировать CDC с помощью triggers или polling
- **Цель**: Change data capture паттерн
- **Входные данные**: OLTP Postgres
- **Результат**: Change log в Kafka/файл
- **Реализация**:
  1. Database triggers для INSERT/UPDATE/DELETE
  2. Запись в changelog таблицу
  3. Polling job для чтения
  4. Публикация в downstream

#### **Task 34: Fraud detection pipeline**
- **Описание**: Real-time обнаружение подозрительных транзакций
- **Цель**: Streaming ML, alerting
- **Входные данные**: Order events stream
- **Результат**: Алерты по fraud
- **Реализация**:
  1. Rule-based scoring (amount, frequency)
  2. Aggregation по user за окно времени
  3. Threshold для алертов
  4. Запись подозрительных в БД

#### **Task 35: Spark job optimization - caching**
- **Описание**: Оптимизировать job с помощью persist/cache
- **Цель**: Performance tuning
- **Входные данные**: Iterative computations
- **Результат**: Ускорение в 3-5 раз
- **Реализация**:
  1. Identify reused DataFrames
  2. cache() или persist(MEMORY_AND_DISK)
  3. unpersist() после использования
  4. Spark UI анализ

#### **Task 36: Data partitioning strategy**
- **Описание**: Подобрать оптимальный partitioning для orders
- **Цель**: Query optimization
- **Входные данные**: Access patterns
- **Результат**: Схема партиционирования
- **Реализация**:
  1. Анализ запросов (по датам, seller_id)
  2. Тестирование разных стратегий
  3. Multi-level partitioning (date/seller)
  4. Benchmarking

#### **Task 37: Small files problem решение**
- **Описание**: Компакция множества мелких файлов в S3
- **Цель**: Storage optimization, I/O
- **Входные данные**: Много маленьких Parquet
- **Результат**: Оптимальные файлы 128-256MB
- **Реализация**:
  1. Spark job для compaction
  2. coalesce() для объединения
  3. Расписание в Airflow
  4. Удаление старых файлов

#### **Task 38: Schema evolution в Parquet**
- **Описание**: Добавить новые колонки без переписывания всех данных
- **Цель**: Schema management
- **Входные данные**: Существующие Parquet файлы
- **Результат**: Совместимость старых/новых схем
- **Реализация**:
  1. mergeSchema option в Spark
  2. Nullable новые колонки
  3. Backwards compatibility
  4. Schema registry (optional)

#### **Task 39: Idempotent pipelines тестирование**
- **Описание**: Доказать идемпотентность через повторные запуски
- **Цель**: Reliability, correctness
- **Входные данные**: Любой DAG
- **Результат**: Тесты идемпотентности
- **Реализация**:
  1. Запустить pipeline 2 раза
  2. Сравнить результаты (checksum)
  3. Проверить отсутствие дублей
  4. Интеграционный тест

#### **Task 40: Custom Airflow operator**
- **Описание**: Создать SparkOperator с кастомной логикой
- **Цель**: Extensibility, reusability
- **Входные данные**: BaseOperator class
- **Результат**: Reusable operator
- **Реализация**:
  1. Extend BaseOperator
  2. Implement execute()
  3. Параметризация
  4. Тестирование

#### **Task 41: Data versioning с Delta Lake (или имитация)**
- **Описание**: Версионирование данных для time-travel
- **Цель**: Data versioning, reproducibility
- **Входные данные**: Orders dataset
- **Результат**: Доступ к историческим версиям
- **Реализация**:
  1. Имитация через партиции по version_id
  2. Metadata таблица с версиями
  3. Query по состоянию на дату
  4. Rollback mechanism

#### **Task 42: Cross-DAG dependencies**
- **Описание**: Настроить зависимости между DAGs
- **Цель**: Complex orchestration
- **Входные данные**: Несколько DAGs
- **Результат**: Порядок выполнения
- **Реализация**:
  1. ExternalTaskSensor
  2. TriggerDagRunOperator
  3. Dataset-based scheduling (Airflow 2.4+)
  4. Error propagation

#### **Task 43: Cost optimization - lifecycle policies**
- **Описание**: Архивация старых данных в cheaper storage
- **Цель**: Cost management
- **Входные данные**: Old partitions
- **Результат**: Снижение затрат на хранение
- **Реализация**:
  1. S3 lifecycle policies для archiving
  2. Компрессия старых файлов (gzip)
  3. Миграция в холодное хранилище
  4. Retention policy enforcement

#### **Task 44: Data catalog с metadata**
- **Описание**: Создать каталог данных с описаниями и метриками
- **Цель**: Governance, discoverability
- **Входные данные**: Все таблицы
- **Результат**: Searchable catalog
- **Реализация**:
  1. Metadata extraction скрипт
  2. Таблица data_catalog
  3. Descriptions, owners, SLAs
  4. Integration с dbt docs

#### **Task 45: Monitoring с Prometheus + Grafana**
- **Описание**: Настроить метрики для пайплайнов
- **Цель**: Observability
- **Входные данные**: Airflow/Spark logs
- **Результат**: Dashboards
- **Реализация**:
  1. Airflow StatsD exporter
  2. Custom metrics в Python
  3. Prometheus scraping
  4. Grafana dashboards

#### **Task 46: SLA monitoring в Airflow**
- **Описание**: Настроить SLA для критичных DAGs
- **Цель**: Reliability, alerting
- **Входные данные**: Business requirements
- **Результат**: SLA alerts
- **Реализация**:
  1. sla parameter в tasks
  2. sla_miss_callback
  3. Email/PagerDuty alerts
  4. SLA dashboard

#### **Task 47: Data quality anomaly detection**
- **Описание**: ML-based обнаружение аномалий в данных
- **Цель**: Proactive quality
- **Входные данные**: Historical metrics
- **Результат**: Автоматические алерты
- **Реализация**:
  1. Статистические модели (Z-score, IQR)
  2. Сравнение с историей
  3. Threshold tuning
  4. Alert on anomalies

#### **Task 48: Multi-environment setup**
- **Описание**: Dev/Staging/Prod окружения
- **Цель**: SDLC best practices
- **Входные данные**: Config per environment
- **Результат**: Isolated environments
- **Реализация**:
  1. Отдельные БД/S3 buckets
  2. Environment variables
  3. Config management
  4. Deployment процесс

#### **Task 49: Disaster recovery plan**
- **Описание**: Backup/restore процедуры
- **Цель**: Business continuity
- **Входные данные**: Критичные данные
- **Результат**: DR runbook
- **Реализация**:
  1. Automated backups (pg_dump)
  2. S3 versioning
  3. Recovery testing
  4. Documentation

#### **Task 50: End-to-end integration test**
- **Описание**: Тест всего пайплайна от source до mart
- **Цель**: Quality assurance
- **Входные данные**: Test dataset
- **Результат**: Automated test suite
- **Реализация**:
  1. Fixture data generation
  2. Pipeline execution
  3. Assertions на результаты
  4. CI/CD integration

---

## ⚙️ Production-аспекты

### Логирование
- **Task 51**: Structured logging во всех компонентах (JSON format)
- **Task 52**: Centralized logging с Elasticsearch/Loki (optional)
- **Task 53**: Log rotation и retention policies

### Тестирование
- **Task 54**: Unit тесты для Python utils (pytest)
- **Task 55**: dbt data tests (not_null, unique, relationships)
- **Task 56**: Integration тесты DAGs
- **Task 57**: Contract тесты для API responses

### CI/CD
- **Task 58**: GitHub Actions для запуска pytest
- **Task 59**: Автоматический dbt test при PR
- **Task 60**: Linting (flake8, black, pylint)
- **Task 61**: Pre-commit hooks

---

## 📈 Roadmap выполнения проекта

### Фаза 1: Фундамент (2 недели)
1. Setup инфраструктуры (Tasks 1)
2. Генерация данных (Tasks 2)
3. Базовые DAGs (Tasks 3, 4, 7)
4. dbt setup (Tasks 5, 8, 9)
5. Первый Spark job (Tasks 6)

### Фаза 2: Core пайплайны (3 недели)
1. Incremental загрузки (Task 11)
2. Dimensional modeling (Tasks 24)
3. Intermediate слой (Task 18)
4. Reporting marts (Tasks 19, 25)
5. Data quality (Tasks 10, 14, 23)

### Фаза 3: Optimization (2 недели)
1. Partitioning (Tasks 12, 36)
2. Spark optimization (Tasks 17, 35, 37)
3. Caching (Task 28)
4. Schema evolution (Task 38)

### Фаза 4: Streaming (2 недели)
1. Kafka setup (Task 31)
2. Spark Streaming (Task 32)
3. CDC (Task 33)
4. Real-time analytics (Task 34)

### Фаза 5: Production (2 недели)
1. Monitoring (Tasks 45, 46)
2. Testing suite (Tasks 54-57)
3. CI/CD (Tasks 58-61)
4. Documentation (Task 27, 44)

### Фаза 6: Advanced (2 недели)
1. Multi-environment (Task 48)
2. Disaster recovery (Task 49)
3. Cost optimization (Task 43)
4. End-to-end tests (Task 50)

**Общее время: ~3 месяца** (при работе вечерами/выходными)

---

## 🎤 Презентация на собеседовании

### Структура рассказа (5-7 минут)

1. **Контекст** (1 мин)
   - "Создал e-commerce analytics platform для демонстрации навыков DE"
   - "Монорепозиторий с полным циклом: ingestion → transformation → serving"

2. **Архитектура** (2 мин)
   - Показать диаграмму
   - Объяснить выбор технологий
   - Batch + Streaming processing

3. **Highlights** (2-3 мин)
   - **Сложная задача 1**: "Реализовал SCD Type 2 для историзации цен"
   - **Сложная задача 2**: "Оптимизировал Spark job с 20 мин до 3 мин через partitioning + broadcast join"
   - **Сложная задача 3**: "Настроил real-time fraud detection на Spark Streaming"

4. **Production качество** (1 мин)
   - "Покрыл тестами: unit (pytest) + data quality (dbt tests) + integration"
   - "CI/CD через GitHub Actions"
   - "Monitoring в Grafana"

5. **Результаты** (30 сек)
   - "60+ задач реализовано"
   - "Полная документация + runbook"
   - "Готово к production deployment"

### Ключевые метрики для упоминания
- Объем данных: "Обрабатываю 1M+ events/day"
- Performance: "Оптимизировал query с 45 сек до 2 сек"
- Reliability: "SLA 99.5% для критичных пайплайнов"
- Cost: "Снизил storage costs на 40% через partitioning + archiving"

---

## ❓ Вопросы на собеседовании и ответы

### Вопрос 1: "Как обеспечить идемпотентность пайплайнов?"

**Ответ**:
- Использую upsert (ON CONFLICT DO UPDATE) вместо INSERT
- Партиционирование по дате + overwrite стратегия
- Unique constraints на business keys
- dbt incremental с merge strategy
- Реализовал тест: запуск 2 раза → одинаковый результат

### Вопрос 2: "Как обрабатываете late arriving data?"

**Ответ**:
- В dbt incremental использую lookback window (3 дня)
- Фильтрую по updated_at, а не ingestion_time
- Watermarking в Spark Streaming для события с задержкой
- Reprocessing job для корректировки aggregations

### Вопрос 3: "Как мониторите data quality?"

**Ответ**:
- dbt tests: not_null, unique, relationships, custom
- Great Expectations для complex rules (в планах)
- Anomaly detection на count/sum метриках
- SLA monitoring в Airflow
- Alerts в Slack при failures

### Вопрос 4: "Почему выбрали именно этот стек?"

**Ответ**:
- **Airflow**: industry standard для orchestration
- **dbt**: best practice для SQL transformations, testability
- **Spark**: необходим для больших данных, распределенная обработка
- **Postgres**: универсальный для OLTP + небольшой DWH
- Все open-source → low barrier для pet-project

### Вопрос 5: "Как оптимизировали Spark jobs?"

**Ответ**:
- Broadcast join для маленьких таблиц (< 10MB)
- Partitioning данных по дате для predicate pushdown
- Cache/persist для reused DataFrames
- Coalesce для уменьшения файлов
- Tune parallelism (spark.sql.shuffle.partitions)
- Мониторю через Spark UI (stages, tasks, shuffle)

### Вопрос 6: "Как справляетесь с schema changes?"

**Ответ**:
- Версионирование схем в git
- dbt schema tests предупреждают об изменениях
- Backwards compatible changes (nullable колонки)
- mergeSchema в Parquet для эволюции
- Communication с upstream teams

### Вопрос 7: "Как бы масштабировали это на production?"

**Ответ**:
- Kubernetes для оркестрации контейнеров
- Managed Airflow (MWAA / Cloud Composer)
- Managed Spark (EMR / Databricks)
- Cloud DWH (Snowflake / BigQuery) вместо Postgres
- Terraform для IaC
- Secrets management (Vault)
- Multi-region для DR

### Вопрос 8: "Какие метрики трекаете?"

**Ответ**:
- **Pipeline health**: success rate, duration, retries
- **Data quality**: null rate, duplicate count, freshness
- **Performance**: query latency, throughput
- **Cost**: storage usage, compute hours
- **Business**: daily revenue, order count

### Вопрос 9: "Опыт с real-time streaming?"

**Ответ**:
- Реализовал Kafka producer/consumer
- Spark Structured Streaming для aggregations
- Window functions (tumbling 5 min)
- Watermarking для late events
- At-least-once delivery гарантии

### Вопрос 10: "Как тестируете pipelines?"

**Ответ**:
- **Unit tests**: pytest для Python utilities
- **Data tests**: dbt tests на модели
- **Integration tests**: end-to-end на тестовых данных
- **Smoke tests**: после deployment
- CI/CD запускает все автоматически

---

## 📚 Дополнительные материалы для README

```markdown
# TechMart Data Platform

E-commerce analytics platform демонстрирующая навыки Data Engineering.

## 🎯 Features
- ✅ Batch & Streaming processing
- ✅ Dimensional modeling (Star schema)
- ✅ Data quality framework
- ✅ Real-time analytics
- ✅ Production-ready orchestration
- ✅ Full test coverage
- ✅ CI/CD automation

## 🚀 Quick Start
```bash
# Clone repo
git clone https://github.com/username/techmart-data-platform

# Start services
make up

# Seed data
make seed

# Run pipelines
make run-dags
```

## 📊 Architecture
[Вставить диаграмму]

## 🧪 Testing
```bash
make test        # All tests
make test-unit   # Unit tests
make test-dbt    # dbt tests
```

## 📈 Metrics
- 1M+ events/day processed
- 99.5% pipeline SLA
- < 5 min end-to-end latency
- 40% storage cost reduction

## 🛠️ Tech Stack
Python | Airflow | dbt | Spark | Kafka | Postgres | Redis | Docker

## 📖 Documentation
See [docs/](./docs/) for detailed documentation.
```

---

## ✅ Чеклист готовности проекта

- [ ] Docker-compose запускается с первого раза
- [ ] Есть seed данные для демонстрации
- [ ] Все DAGs успешно проходят
- [ ] dbt models компилируются
- [ ] Тесты проходят (pytest + dbt)
- [ ] README с инструкциями
- [ ] Диаграмма архитектуры
- [ ] GitHub Actions CI работает
- [ ] Grafana dashboards настроены
- [ ] Есть примеры SQL queries для анализа
- [ ] Documentation в docs/
- [ ] Code покрыт комментариями
- [ ] Git history читаемая (не один коммит)

---

Этот проект демонстрирует **реальные навыки middle data engineer** и готов для обсуждения на собеседованиях. Каждая задача решает конкретную проблему из production окружения.