### 🔴 ADVANCED (20 задач)

#### **Task 41: Data versioning с Delta Lake (или имитация)**
- **Описание**: Версионирование данных для time-travel
- **Цель**: Data versioning, reproducibility
- **Входные данные**: Orders dataset
- **Результат**: Доступ к историческим версиям
- **Реализация**:
  1. Имитация через партиции по version_id
  2. Metadata таблица с версиями
  3. Query по состоянию на дату
  4. Rollback mechanism
