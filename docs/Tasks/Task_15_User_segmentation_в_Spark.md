### 🟡 INTERMEDIATE (20 задач)

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
