### 🔴 ADVANCED (20 задач)

#### **Task 43: Cost optimization - lifecycle policies**
- **Описание**: Архивация старых данных в cheaper storage
- **Цель**: Cost management
- **Входные данные**: Old partitions
- **Результат**: Снижение затрат на хранение
- **Реализация**:
  1. S3 lifecycle policies для archiving
  2. Компрессия старых файлов (gzip)
  3. Миграция в холодное хранилище
  4. Retention policy enforcement
