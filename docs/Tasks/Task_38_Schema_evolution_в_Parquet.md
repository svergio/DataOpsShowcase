### 🔴 ADVANCED (20 задач)

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
