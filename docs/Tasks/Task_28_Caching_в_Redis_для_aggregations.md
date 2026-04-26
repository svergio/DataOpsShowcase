### 🟡 INTERMEDIATE (20 задач)

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
