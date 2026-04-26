### 🟡 INTERMEDIATE (20 задач)

#### **Task 18: Intermediate слой в dbt**
- **Описание**: Создать int_orders_enriched с расширенной информацией
- **Цель**: Модульность, reusability
- **Входные данные**: stg_orders, dim_users, dim_products
- **Результат**: Enriched orders для нескольких marts
- **Реализация**:
  1. JOIN нескольких dimensions
  2. Добавить вычисляемые поля
  3. Использовать в нескольких marts
  4. Ephemeral vs table materialization
