# Дорожная карта DataOpsShowcase

Документ задаёт **приоритеты развития** песочницы и **детальное ТЗ-направления** (из продуктового бэклога TechMart) на ближайшее время. Текущий стек, DAG и схемы DWH: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md), [PIPELINES.md](PIPELINES.md), [diagrams/dwh-schemas.md](diagrams/dwh-schemas.md).

## Контекст: бизнес-образ TechMart

**Описание:** интернет-магазин электроники в модели **marketplace**. Аналитическая платформа призвана закрывать:

- анализ продаж в реальном времени;
- рекомендательные сценарии;
- antifraud-задачи;
- управление остатками;
- аналитику эффективности продавцов.

**Источники (логически):**

- OLTP PostgreSQL (`orders`, `users`, `products`, `sellers`);
- потоковые события (clickstream, корзина, поиск);
- внешние API (курсы валют, трекинг доставок);
- CSV/файлы обновлений каталога от продавцов.

**Слойность (упрощённо):** источники → ingestion → storage → transformation → serving → monitoring (детализация в [ARCHITECTURE.md](ARCHITECTURE.md)).

---

## 15 направлений доработки на ближайшее время

Ниже — **подробные** постановки: цель, требования, ориентиры по хранению. Имена схем/таблиц — **целевые** для эволюции стенда; фактическая реализация по мере сил.

### Блок A — ETL/ELT (10 направлений)

#### 1) Customer 360: identity resolution

**Цель:** собрать **единый профиль клиента** из нескольких источников (идея — до 7 в полной постановке).

**Требования:**

- Ingest: PostgreSQL (OLTP), в перспективе внешние API (например CRM), Kafka `events.auth` (по сценарию), S3/MinIO raw;
- дедупликация: deterministic → probabilistic (например, сходство TF-IDF для ФИО/адреса);
- хранилище: зона curated (в полной постановке — Iceberg `curated.customer_360`; в стенде — эквивалент витрин/слоя marts);
- инкрементальность: CDC (Debezium) + merge-on-read **или** watermark-паттерн, совместимый с текущими DAG;
- ориентир по SLA: менее 15 минут от события до актуального профиля (цель дизайна, не гарантия стенда).

#### 2) Multi-currency revenue normalization

**Цель:** привести выручку к **сопоставимому виду** в разных валютах.

**Требования:**

- источники: OLTP `orders`, внешнее API курсов;
- инкрементальность: курсор по `updated_at` / граница пересчёта;
- обработка отложенных/исправленных заказов через очередь перерасчёта (логически);
- выходные поля: `revenue_converted`, `fx_gap`, `fx_type`;
- запись: `analytics.revenue_daily` (или `dwh_marts` / соглашения проекта).

#### 3) Marketing attribution (touchpoint joiner)

**Цель:** связать **touchpoint → session → conversion**.

**Требования:**

- источники: Kafka (витрина web/mobile), сырые события в S3, конверсии из CRM-эквивалента;
- join: окно 7 дней, watermark 48 ч (как дизайн-ориентир);
- реализация: Spark Structured Streaming **или** batch с тем же смыслом;
- выход: `mart.attribution_first_touch` (имя витрины — согласовать с `dbt`).

#### 4) Product recommendation: inventory sync

**Цель:** отражать **фактическую доступность** товаров для поиска и ML.

**Требования:**

- агрегировать `warehouse.stock` и `warehouse.reservations` (или эквиваленты в стенде);
- метрика `inventory_score`, обновление с throttling (например, только изменившиеся SKU, цикл 5 минут);
- destination: Redis + Iceberg/витрина (в стенде — marts + при необходимости Redis).

#### 5) Risk scoring: transactions + behavior

**Цель:** подготовка **признаков** для real-time antifraud (или near-real-time).

**Требования:**

- источники: Kafka `transactions`, `login_events`, `device_fingerprint` (по сценарию);
- признаки: frequency, velocity, `unusual_device`, `ip_novelty`;
- справочники: GeoIP, BIN lookup (подключаемо внешними справочниками);
- выход: `features.risk_factors` (feature store / marts в упрощении).

#### 6) Streaming SLA monitor

**Цель:** **контроль задержек** потоковых пайплайнов.

**Требования:**

- метрики: consumer lag, возраст watermark, p90 processing time;
- интеграция: Prometheus + Grafana;
- вебхуки: PagerDuty/Slack при нарушении SLA (в стенде — шаблон алертов);
- хранение: `monitoring.streaming_sla` (или `meta` + витрина).

#### 7) Product taxonomy rebuilder

**Цель:** **восстанавливать иерархию** товаров из разрозненных тегов.

**Требования:**

- источники: ручные теги, категории поставщиков, ML-предсказания;
- алгоритм: greedy tree rebuild + rule-based overrides;
- ночной batch;
- хранение: `dim.product_taxonomy_v2` (или marts-эквивалент в dbt).

#### 8) Enriched order lifecycle

**Цель:** единая модель **жизненного цикла заказа** по событиям.

**Требования:**

- join: оплаты, доставка, возвраты, тикеты поддержки;
- state machine: created → paid → shipped → delivered → closed;
- SLA: сутки batch + микро-batch почасово (ориентир);
- destination: `mart.order_lifecycle`.

#### 9) Supplier KPI: reliability

**Цель:** **качество поставщиков** (своевременность, дефекты, отмены).

**Требования:**

- KPI: on-time delivery, defect ratio, cancellation ratio;
- источники: логистика, QC, `supply_contracts` (в упрощении — из доступных сущностей);
- инкрементальность: курсор по `event_time`;
- хранение: `analytics.supplier_kpi` / marts.

#### 10) Anomaly detection in metrics

**Цель:** **автоматически** находить аномалии в операционных метриках.

**Требования:**

- источник: экспорт метрик Prometheus;
- подход: STL + z-score (или сопоставимый);
- Airflow: периодичность, например 30 мин;
- сигналы: Slack + `monitoring.metric_anomalies` (таблица/витрина).

---

### Блок B — ML (5 направлений)

#### 11) Churn probability (classification)

- датасет: поведенческие события + история оплат;
- выход: `churn_score` [0, 1];
- модель: LightGBM (или аналог);
- retrain: еженедельно (расписание в Airflow/MLflow).

#### 12) Dynamic pricing: elasticity estimator

- метрика: изменение спроса при изменении цены;
- модель: Bayesian Elasticity Regression (или упрощённый регрессионный бейзлайн);
- выход: `features.price_elasticity` / marts.

#### 13) Delivery time prediction (regression)

- источники: исторические доставки, погодные/нагрузочные факторы (по мере появления);
- модель: CatBoost Regressor (пример);
- целевое качество: MAE менее 18 минут (целевой ориентир).

#### 14) Fraud risk: rule booster (ML + rules)

- генерация **кандидатных** правил через ML;
- модель: Decision Tree, глубина ≤ 4;
- экспорт правил в **YAML** для согласования с бизнесом.

#### 15) Text classification: support ticket routing

- модель: DistilBERT (или лёгкий энкодер в стенде);
- классы: `billing`, `product_bug`, `logistics_issue`, `general_question` (расширяемо);
- выход: `predicted_category` в feature/marts слое.

**Связь с репо:** точки входа [ML.md](ML.md), DAG `dag_ml_train_spark`, [PIPELINES.md](PIPELINES.md).

---

### Блок C — Платформа, качество, observability (сквозняк)

#### dbt

- тесты: `freshness`, `unique`, `not_null` на критичных моделях;
- для критичных: `severity: error` (см. `dbt_project`);
- `dbt docs` в CI, артефакты;
- dbt-web в compose (текущее состояние: [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md));
- webhooks Airflow → dbt-web (события готовности слоёв) — по мере внедрения.

#### Data quality

- SLA: задержка ingestion, **обнаружение дрейфа схем**;
- мониторинг метаданных: row count, min/max, null%;
- агрегаты в `monitoring.data_quality` или `meta` / `dwh_dq` (согласовать с [diagrams/dwh-schemas.md](diagrams/dwh-schemas.md)).

#### Observability

- OpenLineage (или аналог) для **data lineage** end-to-end;
- алерты Prometheus: lag, падения микро-batch;
- SLA-дашборды в Grafana.

---

## Сопоставление с приоритетами P0 / P1 / P2

| Приоритет | Фокус |
|-----------|--------|
| **P0** | Стабильный compose, ingress, [dbt-web](WEB_UI_ACCESS.md) и [API](API.md); dbt-тесты и `store_failures` в `dwh_dq`; `meta.*` (прогоны, watermarks); базовые дашборды. Без надёжной базы детальные пункты 1–15 **не** демонстрируются. |
| **P1** | Поэтапная реализация **блока A (1–10)** и **блока B (11–15)** в виде MVP: один-два сценария ETL, один ML-пилот, расширение [Generators.md](Generators.md) и [business/use_cases.md](business/use_cases.md). |
| **P2** | **Блок C** в полноте: OpenLineage, сильный CI, каталог метрик, алерты в мессенджеры, model registry, мультиарендность не требуется. |

**Как читать ближайшее время:** в первую очередь — **стабилизация P0**, затем **выбранные** пункты из блоков A и B (не все 15 сразу), параллельно наращивать **блок C** по мере зрелости.

---

## Ссылки

| Документ | Назначение |
|----------|------------|
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Стек и поток данных |
| [PIPELINES.md](PIPELINES.md) | Текущие DAG |
| [business/value.md](business/value.md) | Ценность песочницы |

*Обновляйте дорожную карту вместе с крупными PR: по мере внедрения закрывайте отдельные подпункты и ссылайтесь на коммит/релиз.*
