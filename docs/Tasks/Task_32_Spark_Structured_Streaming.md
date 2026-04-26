### 🔴 ADVANCED (20 задач)

#### **Task 32: Spark Structured Streaming**
- **Описание**: Real-time aggregation событий с помощью Spark Streaming
- **Цель**: Streaming processing
- **Входные данные**: Kafka topic
- **Результат**: Realtime метрики в Redis
- **Реализация**:
  1. readStream from Kafka
  2. Window aggregations (tumbling, sliding)
  3. Watermarking для late data
  4. writeStream to Redis/Postgres
