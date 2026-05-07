# Бизнес-метрики TechMart

Документ задает единый словарь метрик и текущее покрытие в DWH. Формат: **метрика → как считать → какие поля нужны → статус покрытия**.

Статусы покрытия:
- `ready` — данные есть в текущих слоях.
- `partial` — часть данных есть, расчет ограничен.
- `gap` — данных недостаточно, нужна доработка источников/модели.

## 1) Top-line

| Метрика | Как считать | Нужные поля | Статус |
|---|---|---|---|
| GMV | `SUM(total_amount)` | заказ, сумма заказа | ready |
| Net Revenue | `SUM(paid_amount)` | оплаченная сумма | ready |
| Кол-во заказов | `COUNT(DISTINCT order_hub_key)` | идентификатор заказа | ready |
| AOV | `SUM(total_amount) / COUNT(DISTINCT order_hub_key)` | сумма, заказ | ready |
| Кол-во покупателей | `COUNT(DISTINCT customer_hub_key)` | идентификатор покупателя | ready |
| New vs Repeat buyers | first order date vs текущий день | покупатель, дата заказа | ready |
| Возвраты / скидки / комиссии | вычитание из GMV | refunds, discounts, commissions | gap |

## 2) Retention and Engagement

| Метрика | Как считать | Нужные поля | Статус |
|---|---|---|---|
| Cohort retention (D1/D7/D30/D90) | активные покупатели / размер когорты | покупатель, дата первой/повторной покупки | ready |
| Rolling retention | активность после первой покупки | покупатель, даты покупок | ready |
| Purchase frequency | `orders per customer` | заказ, покупатель | ready |
| Days since last purchase | `current_date - max(order_date)` | покупатель, дата заказа | ready |
| Add to cart / conversion funnel | view -> cart -> purchase | product view/add-to-cart events | gap |
| Abandonment rate | abandoned carts / carts | cart lifecycle events | gap |

## 3) Unit-экономика

| Метрика | Как считать | Нужные поля | Статус |
|---|---|---|---|
| LTV (30/90/180/365) | cumulative revenue per customer window | покупатель, выручка, дата | ready |
| CAC | acquisition spend / new customers | spend по каналу/когорте, new buyers | gap |
| LTV/CAC | `LTV / CAC` | LTV + CAC | gap |
| Payback period | момент, когда LTV >= CAC | LTV trajectory + CAC | gap |
| Contribution margin | revenue - variable costs | costs per order/customer | gap |
| Average order margin | margin / orders | order-level margin | gap |

## 4) Продуктовые и категорийные

| Метрика | Как считать | Нужные поля | Статус |
|---|---|---|---|
| Конверсия по категориям | orders / category exposures | заказы + экспозиции/просмотры | partial |
| Топ товаров по выручке | `SUM(line_revenue) by product` | товары в заказе, выручка | ready |
| Топ товаров по марже | `SUM(margin) by product` | себестоимость/маржа | gap |
| % возвратов по категориям/брендам | returns / orders by category | возвраты + категория/бренд | gap |
| Среднее число товаров в заказе | `AVG(total_quantity)` | количество позиций | ready |
| Cross-sell / Upsell | связки товаров, attach rate | order_items product pairs | partial |

## 5) Маркетинг

| Метрика | Как считать | Нужные поля | Статус |
|---|---|---|---|
| ROAS | attributed revenue / ad spend | spend + атрибуция заказов | gap |
| Доля трафика по источникам | sessions by source | сессии и source | gap |
| Конверсия по каналам | orders / sessions by channel | канал, сессии, заказы | gap |
| Бюджет кампаний | `SUM(budget)` | marketing campaigns table | ready |

## Текущее покрытие источников (аудит)

- `raw.oltp_orders`, `raw.oltp_order_items`, `raw.kafka_payments`: есть основа для продаж, покупателей и частоты.
- `raw.oltp_marketing_campaigns`: есть метаданные кампаний и бюджеты, но нет корректной атрибуции revenue к каналам.
- Нет полноценных событий корзины/просмотров для классической e-commerce воронки.
- Нет фактов переменных затрат и возвратов в формате, достаточном для unit-economics и return-rate.

## Что реализовано в этой волне

- Витрины бизнес-метрик на доступных данных (Top-line, retention, category/performance, LTV windows).
- Маркетинг и unit-economics с `partial/gap` полями оставлены с явными `NULL`/ограничениями, чтобы не маскировать отсутствие данных.

## Где смотреть в UI

- Superset dashboard: `/superset/dashboard/techmart-business-metrics-kpis/`
- Grafana dashboard UID: `business-kpis` (панель `Business KPIs`)
- Airflow DAG для сборки: `dag_dbt_business_kpis_rest`

## Связка метрика → витрина

| Группа метрик | Основная витрина |
|---|---|
| Top-line | `dwh_marts.mart_daily_business_kpis` |
| Retention | `dwh_marts.mart_cohort_retention` |
| Frequency/RFM | `dwh_marts.mart_user_rfm` |
| Product/Category | `dwh_marts.mart_category_performance` |
| Marketing coverage | `dwh_marts.mart_marketing_channel` |
| Unit economics | `dwh_marts.mart_unit_economics` |
