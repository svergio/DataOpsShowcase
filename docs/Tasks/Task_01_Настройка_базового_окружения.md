### 🟢 BEGINNER (10 задач)

#### **Task 1: Настройка базового окружения**
- **Описание**: Создать docker-compose с Postgres, Airflow, MinIO
- **Цель**: Понимание инфраструктуры, Docker
- **Входные данные**: docker-compose.yml template
- **Результат**: Поднятое окружение, доступ к UI Airflow
- **Реализация**:
  1. Создать docker-compose.yml с сервисами
  2. Настроить volumes для персистентности
  3. Создать init скрипты для Postgres
  4. Добавить healthchecks
