### 🟢 BEGINNER (10 задач)

#### **Task 8: Создание dimensions в dbt**
- **Описание**: Создать dim_users, dim_products из staging
- **Цель**: Dimensional modeling
- **Входные данные**: stg_users, stg_products
- **Результат**: Таблицы marts.dim_*
- **Реализация**:
  1. Добавить surrogate keys (dbt_utils.surrogate_key)
  2. Выбрать нужные атрибуты
  3. Добавить created_at, updated_at
  4. Тесты на уникальность
