# FAQ: для стейкхолдеров и инженеров

## Для стейкхолдеров

### Это production?
Нет. Это sandbox/demo-платформа с production-подходами. Цель - быстро проверять архитектурные и бизнес-гипотезы, не подменяя полноценный enterprise-контур.

### Почему тогда ей можно доверять в демо?
Потому что есть воспроизводимый E2E-поток (ingestion -> DWH -> витрины), наблюдаемость и базовые quality checks. Уровень доверия ограничен рамками стенда и явно отражён в gaps/roadmap.

### Какой главный бизнес-результат от платформы?
Сокращение времени от бизнес-вопроса до проверяемого ответа через стандартизированные витрины, мониторинг и повторяемые сценарии use cases.

### Что нужно, чтобы перейти к production-like режиму?
Закрыть P0/P1 gaps: формализовать SLO и ownership, усилить release-gates и incident process, закрепить security/access governance.

## Для инженеров

### Где смотреть архитектуру и поток данных?
- Общая картина: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- Структура репозитория: [ARCHITECTURE.md](ARCHITECTURE.md)
- Диаграммы: [diagrams/README.md](diagrams/README.md)

### Какой минимальный operational-check перед релизом?
Smoke ingress + health ключевых сервисов + dbt DQ + проверка свежести витрин + rollback-checklist. Детали: [QUALITY_AND_MONITORING.md](QUALITY_AND_MONITORING.md).

### Где искать причины падения DAG?
Базовый маршрут: [runbook/AIRFLOW_DAG_TROUBLESHOOTING.md](runbook/AIRFLOW_DAG_TROUBLESHOOTING.md), затем метрики/логи из [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md).

### Как отличить проблему данных от проблемы оркестрации?
Если DAG зелёный, но метрики/витрины неверные - начинать с DQ и dbt-тестов. Если DAG падает/запаздывает - сначала оркестрация, dependency chain и инфраструктурные метрики.

### Какие ограничения у NL2SQL в текущем виде?
Это вспомогательный слой для стенда, не замена governed BI. Для production-режима нужны policy guardrails (read-only, whitelist, audit, limits) и governance.

### Что считается "готово" по use case?
Есть owner, baseline KPI, целевой KPI и acceptance criteria; сценарий встроен в roadmap и связан с источниками/витриной/мониторингом.

## См. также

- [business/use_cases.md](business/use_cases.md)
- [GAPS_AND_PRODUCTION_READINESS.md](GAPS_AND_PRODUCTION_READINESS.md)
- [Roadmap.md](Roadmap.md)
