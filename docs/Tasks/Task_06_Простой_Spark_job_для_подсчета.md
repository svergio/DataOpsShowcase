### 🟢 BEGINNER (10 задач)

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
