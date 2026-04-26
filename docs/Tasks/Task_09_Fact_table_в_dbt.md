### 🟢 BEGINNER (10 задач)

#### **Task 9: Fact table в dbt**
- **Описание**: Создать fct_orders с foreign keys на dimensions
- **Цель**: Star schema
- **Входные данные**: stg_orders + dimensions
- **Результат**: marts.fct_orders
- **Реализация**:
  1. JOIN staging с dimensions
  2. Выбрать measures (amount, quantity)
  3. Добавить grain (order_id)
  4. Relationships тесты
