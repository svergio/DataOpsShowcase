### 🟢 BEGINNER (10 задач)

#### **Task 4: Загрузка CSV файлов из S3 в Postgres**
- **Описание**: DAG который читает CSV из S3 и загружает в raw schema Postgres
- **Цель**: Reverse flow, bulk insert
- **Входные данные**: CSV в S3
- **Результат**: Таблица raw.orders_raw
- **Реализация**:
  1. S3Sensor для ожидания файла
  2. Pandas для чтения CSV
  3. SQLAlchemy bulk insert
  4. Логирование количества строк
