### 🟡 INTERMEDIATE (20 задач)

#### **Task 25: Product funnel analysis**
- **Описание**: Построить воронку: view → cart → purchase
- **Цель**: Funnel analysis, CTR расчеты
- **Входные данные**: events таблица
- **Результат**: marts.product_funnel
- **Реализация**:
  1. Window functions для упорядочивания событий
  2. CASE для определения стадий
  3. Конверсии между стадиями
  4. Group by product
