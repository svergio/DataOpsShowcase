### 🟡 INTERMEDIATE (20 задач)

#### **Task 13: CDC с помощью dbt snapshots**
- **Описание**: Отслеживать изменения цен продуктов с помощью dbt snapshots
- **Цель**: SCD Type 2, история изменений
- **Входные данные**: products таблица
- **Результат**: snapshots.product_prices_snapshot
- **Реализация**:
  1. Создать snapshot с timestamp strategy
  2. Настроить updated_at column
  3. Запускать в DAG ежедневно
  4. Анализировать изменения
