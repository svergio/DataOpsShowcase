### 🟡 INTERMEDIATE (20 задач)

#### **Task 14: Data quality framework**
- **Описание**: Создать custom dbt tests для бизнес-правил
- **Цель**: Data contracts, quality assurance
- **Входные данные**: Бизнес-правила (order amount > 0)
- **Результат**: Кастомные тесты в macros/
- **Реализация**:
  1. Создать generic test в macros
  2. Параметризация теста
  3. Применить к моделям в .yml
  4. Интеграция в CI/CD
