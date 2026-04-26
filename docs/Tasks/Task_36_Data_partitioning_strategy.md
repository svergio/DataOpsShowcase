### 🔴 ADVANCED (20 задач)

#### **Task 36: Data partitioning strategy**
- **Описание**: Подобрать оптимальный partitioning для orders
- **Цель**: Query optimization
- **Входные данные**: Access patterns
- **Результат**: Схема партиционирования
- **Реализация**:
  1. Анализ запросов (по датам, seller_id)
  2. Тестирование разных стратегий
  3. Multi-level partitioning (date/seller)
  4. Benchmarking
