### 🔴 ADVANCED (20 задач)

#### **Task 42: Cross-DAG dependencies**
- **Описание**: Настроить зависимости между DAGs
- **Цель**: Complex orchestration
- **Входные данные**: Несколько DAGs
- **Результат**: Порядок выполнения
- **Реализация**:
  1. ExternalTaskSensor
  2. TriggerDagRunOperator
  3. Dataset-based scheduling (Airflow 2.4+)
  4. Error propagation
