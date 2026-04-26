### 🟢 BEGINNER (10 задач)

#### **Task 10: Базовый data quality check**
- **Описание**: DAG который проверяет количество записей, null values
- **Цель**: Data observability
- **Входные данные**: marts tables
- **Результат**: Алерт если checks failed
- **Реализация**:
  1. SQLCheckOperator в Airflow
  2. Queries для проверки
  3. Email alert при failure
  4. Логирование результатов

---

### 🟡 INTERMEDIATE (20 задач)
