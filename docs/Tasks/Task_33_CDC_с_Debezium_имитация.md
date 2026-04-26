### 🔴 ADVANCED (20 задач)

#### **Task 33: CDC с Debezium (имитация)**
- **Описание**: Симулировать CDC с помощью triggers или polling
- **Цель**: Change data capture паттерн
- **Входные данные**: OLTP Postgres
- **Результат**: Change log в Kafka/файл
- **Реализация**:
  1. Database triggers для INSERT/UPDATE/DELETE
  2. Запись в changelog таблицу
  3. Polling job для чтения
  4. Публикация в downstream
