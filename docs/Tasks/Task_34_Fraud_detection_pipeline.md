### 🔴 ADVANCED (20 задач)

#### **Task 34: Fraud detection pipeline**
- **Описание**: Real-time обнаружение подозрительных транзакций
- **Цель**: Streaming ML, alerting
- **Входные данные**: Order events stream
- **Результат**: Алерты по fraud
- **Реализация**:
  1. Rule-based scoring (amount, frequency)
  2. Aggregation по user за окно времени
  3. Threshold для алертов
  4. Запись подозрительных в БД
