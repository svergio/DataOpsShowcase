### 🔴 ADVANCED (20 задач)

#### **Task 35: Spark job optimization - caching**
- **Описание**: Оптимизировать job с помощью persist/cache
- **Цель**: Performance tuning
- **Входные данные**: Iterative computations
- **Результат**: Ускорение в 3-5 раз
- **Реализация**:
  1. Identify reused DataFrames
  2. cache() или persist(MEMORY_AND_DISK)
  3. unpersist() после использования
  4. Spark UI анализ
