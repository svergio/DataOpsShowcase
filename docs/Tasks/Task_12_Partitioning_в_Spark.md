### 🟡 INTERMEDIATE (20 задач)

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
