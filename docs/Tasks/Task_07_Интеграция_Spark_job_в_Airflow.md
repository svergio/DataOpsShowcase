### 🟢 BEGINNER (10 задач)

#### **Task 7: Интеграция Spark job в Airflow**
- **Описание**: Создать DAG который запускает Spark job через SparkSubmitOperator
- **Цель**: Orchestration Spark jobs
- **Входные данные**: Spark job скрипт
- **Результат**: Автоматический запуск Spark job
- **Реализация**:
  1. Настроить Spark connection в Airflow
  2. Использовать SparkSubmitOperator
  3. Передать параметры через --conf
  4. Обработать успех/неудачу
