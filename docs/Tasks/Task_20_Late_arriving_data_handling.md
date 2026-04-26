### 🟡 INTERMEDIATE (20 задач)

#### **Task 20: Late arriving data handling**
- **Описание**: Обработка заказов которые пришли с задержкой
- **Цель**: Idempotency, correctness
- **Входные данные**: Orders с разными created_at
- **Результат**: Корректные агрегации
- **Реализация**:
  1. Использовать updated_at вместо ingestion time
  2. Lookback window в incremental
  3. Merge strategy в dbt
  4. Тестирование на идемпотентность
