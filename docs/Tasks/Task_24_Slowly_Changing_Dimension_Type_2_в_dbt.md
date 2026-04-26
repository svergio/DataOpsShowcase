### 🟡 INTERMEDIATE (20 задач)

#### **Task 24: Slowly Changing Dimension Type 2 в dbt**
- **Описание**: SCD2 для user addresses (историзация)
- **Цель**: Advanced dimensional modeling
- **Входные данные**: stg_user_addresses
- **Результат**: dim_user_addresses с valid_from/to
- **Реализация**:
  1. Использовать dbt snapshots или custom logic
  2. Добавить is_current flag
  3. valid_from, valid_to dates
  4. Surrogate key для версий
