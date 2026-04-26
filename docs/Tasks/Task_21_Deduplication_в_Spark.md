### 🟡 INTERMEDIATE (20 задач)

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
