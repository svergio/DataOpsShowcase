### 🟡 INTERMEDIATE (20 задач)

#### **Task 27: Data lineage documentation**
- **Описание**: Генерация дата-линейности с помощью dbt docs
- **Цель**: Documentation, governance
- **Входные данные**: dbt project
- **Результат**: dbt docs site
- **Реализация**:
  1. Добавить descriptions в .yml
  2. Генерировать dbt docs generate
  3. dbt docs serve для визуализации
  4. Интеграция в CI для автообновления
