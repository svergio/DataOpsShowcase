# Atlas / CDC lineage (Airflow)

Настройка lineage-бэкенда задаётся через `AIRFLOW__LINEAGE__BACKEND` и `AIRFLOW__LINEAGE__BACKEND_KWARGS`. Для публикации в Atlas по REST проще добавить свой класс бэкенда в отдельном модуле и указать его в этих переменных; временные проверки — через отдельные задачи/job, пока контракт payload к Atlas не зафиксирован.
