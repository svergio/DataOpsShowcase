### 🔴 ADVANCED (20 задач)

#### **Task 31: Real-time streaming с Kafka**
- **Описание**: Настроить Kafka producer/consumer для clickstream
- **Цель**: Streaming architecture
- **Входные данные**: Симулированные клики
- **Результат**: Events в Kafka topics
- **Реализация**:
  1. Kafka producer для генерации событий
  2. Topic partitioning по user_id
  3. Consumer group для обработки
  4. At-least-once delivery
