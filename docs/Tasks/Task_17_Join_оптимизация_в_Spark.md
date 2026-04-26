### 🟡 INTERMEDIATE (20 задач)

#### **Task 17: Join оптимизация в Spark**
- **Описание**: Оптимизировать join большой и малой таблицы
- **Цель**: Broadcast join, shuffle optimization
- **Входные данные**: Orders (большая) + Products (малая)
- **Результат**: Ускоренный join
- **Реализация**:
  1. Использовать broadcast() для малой таблицы
  2. Сравнить explain() до/после
  3. Настроить spark.sql.autoBroadcastJoinThreshold
  4. Измерить время выполнения
