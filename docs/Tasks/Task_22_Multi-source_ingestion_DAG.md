### 🟡 INTERMEDIATE (20 задач)

#### **Task 22: Multi-source ingestion DAG**
- **Описание**: DAG который читает из API, CSV, и Postgres одновременно
- **Цель**: Orchestration, parallel execution
- **Входные данные**: Разные источники
- **Результат**: Данные в raw schema
- **Реализация**:
  1. Параллельные tasks для каждого источника
  2. Использовать task groups
  3. Downstream task для объединения
  4. Error handling для каждого источника
