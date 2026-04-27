# Data Platform Pet-Project: платформа аналитики e-commerce

## Бизнес-кейс: маркетплейс TechMart

**Описание**: интернет-магазин электроники в модели marketplace. Нужна аналитическая платформа для:

- анализа продаж в реальном времени;
- рекомендательных сценариев;
- antifraud задач;
- управления остатками;
- аналитики эффективности продавцов.

**Источники данных**:

- OLTP PostgreSQL (`orders`, `users`, `products`, `sellers`);
- event stream (clickstream, cart events, search queries);
- внешние API (курсы валют, shipment tracking);
- CSV-файлы с обновлениями каталогов от продавцов.

---

## Архитектура системы

```text
DATA SOURCES -> INGESTION -> STORAGE -> TRANSFORMATION -> SERVING -> MONITORING
```

Слои:

- `ingestion`: Airflow DAG, Spark Streaming, Kafka consumers, Python jobs;
- `storage`: S3/MinIO raw zone, PostgreSQL DWH, Redis cache/state;
- `transformation`: dbt + Spark jobs;
- `serving`: marts в PostgreSQL, кэш в Redis, API-слой;
- `monitoring`: Airflow, Prometheus/Grafana, дашборды.

---

## ETL/ELT пайплайны (10)

### 1) Customer 360 Identity Resolution

**Цель**: собрать единый профиль клиента из 7 источников.

**Требования**:

- Ingest: PostgreSQL (OLTP), Salesforce API, Kafka `events.auth`, S3 raw;
- дедупликация: deterministic -> probabilistic (TF-IDF similarity);
- хранилище: Iceberg `curated.customer_360`;
- инкрементальность: CDC (Debezium) + merge-on-read;
- SLA: < 15 минут от события до актуального профиля.

### 2) Multi-Currency Revenue Normalization

**Цель**: стандартизировать выручку в разных валютах.

**Требования**:

- источники: OLTP `orders`, внешнее API курсов валют;
- инкрементальность: cursor по `updated_at`;
- отложенные заказы обрабатывать через reprocessing queue;
- поля: `revenue_converted`, `fx_gap`, `fx_type`;
- запись: `analytics.revenue_daily`.

### 3) Marketing Attribution (Touchpoint Joiner)

**Цель**: связать touchpoint -> session -> conversion.

**Требования**:

- источники: Kafka `web.events`, mobile events (S3), CRM conversions;
- join window: 7 дней, watermark: 48 часов;
- реализация: Spark Structured Streaming;
- выход: `mart.attribution_first_touch`.

### 4) Product Recommendation Inventory Sync

**Цель**: отражать фактическую доступность товаров для ML-поиска.

**Требования**:

- агрегировать `warehouse.stock` и `warehouse.reservations`;
- вычислять `inventory_score`;
- обновление каждые 5 минут только по изменившимся SKU;
- destination: Redis + Iceberg.

### 5) Risk Scoring (Transactions + Behavior)

**Цель**: подготовка факторов для real-time antifraud.

**Требования**:

- источники: Kafka `transactions`, `login_events`, `device_fingerprint`;
- признаки: frequency, velocity, unusual_device, ip_novelty;
- справочники: GeoIP, BIN lookup;
- выход: feature-store `features.risk_factors`.

### 6) Streaming SLA Monitor

**Цель**: контроль задержек пайплайнов.

**Требования**:

- метрики: consumer lag, watermark age, processing time p90;
- интеграция: Prometheus + Grafana;
- вебхуки: PagerDuty при нарушении SLA;
- хранение: `monitoring.streaming_sla`.

### 7) Product Taxonomy Rebuilder

**Цель**: автоматическое восстановление иерархии товаров.

**Требования**:

- источники: ручные теги, vendor categories, ML-предсказания;
- алгоритм: greedy tree rebuild + rule-based overrides;
- обновление: ночной batch;
- хранение: `dim.product_taxonomy_v2`.

### 8) Enriched Order Lifecycle

**Цель**: собрать полный жизненный цикл заказа по событиям.

**Требования**:

- join: payment, shipment, returns, support tickets;
- state machine: created -> paid -> shipped -> delivered -> closed;
- SLA: daily batch + hourly micro-batch;
- destination: `mart.order_lifecycle`.

### 9) Supplier KPI Reliability

**Цель**: аналитика качества поставщиков.

**Требования**:

- KPI: on-time delivery, defect ratio, cancellation ratio;
- источники: logistics events, QC results, supply_contracts;
- инкрементальность: cursor по `event_time`;
- хранение: `analytics.supplier_kpi`.

### 10) Anomaly Detection in Metrics

**Цель**: автоматический поиск аномалий в метриках.

**Требования**:

- источник: Prometheus metrics export;
- модель: STL decomposition + z-score;
- запуск: Airflow DAG каждые 30 минут;
- сигналы: Slack webhook + `monitoring.metric_anomalies`.

---

## Мини ML-задачи (5)

1. **Churn Probability Model** (classification):
   - dataset: behavioral events + payments history;
   - выход: `churn_score` [0..1];
   - модель: LightGBM;
   - retrain: еженедельно.

2. **Dynamic Pricing Elasticity Estimator**:
   - метрика: изменение спроса при изменении цены;
   - модель: Bayesian Elasticity Regression;
   - выход: `features.price_elasticity`.

3. **Delivery Time Prediction** (regression):
   - источники: исторические доставки + погода + загруженность;
   - модель: CatBoost Regressor;
   - целевая ошибка: MAE < 18 минут.

4. **Fraud Risk Rule Booster** (hybrid ML + rules):
   - генерация candidate rules через ML;
   - модель: Decision Tree, глубина <= 4;
   - экспорт правил в YAML.

5. **Text Classification: Support Ticket Routing**:
   - модель: DistilBERT;
   - классы: `billing`, `product_bug`, `logistics_issue`, `general_question`;
   - выход: `predicted_category`.

---

## TODO: Infrastructure & Governance

### 1) dbt

- Включить tests: `freshness`, `unique`, `not_null`.
- Для критичных тестов: `severity: error`.
- Настроить `dbt docs` в CI/CD (build artifacts).
- Поднять `dbt-web` в `docker-compose`.
- Подключить Airflow webhooks -> dbt-web.

### 2) Data Quality

- SLA: ingestion delay, schema drift detection.
- Мониторинг метаданных: row count, min/max, null%.
- Выгрузка результатов в `monitoring.data_quality`.

### 3) Observability

- Интеграция OpenLineage.
- Prometheus alerts: lag, micro-batch failures.
- SLA dashboards.
