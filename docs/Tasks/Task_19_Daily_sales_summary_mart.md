### 🟡 INTERMEDIATE (20 задач)

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
