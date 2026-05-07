# Gaps и production readiness

Документ фиксирует, что ещё требуется до production-ready состояния. Формулировки ниже являются **target state** для планирования и не утверждают, что это уже реализовано.

## Резюме по зрелости

- Текущий статус: сильная demo/sandbox база с рабочим E2E-контуром и observability.
- Основной разрыв: неформализованные SLO/операционный процесс релизов и инцидентов как обязательный стандарт.
- Второй разрыв: security/governance и политика доступа описаны частично, но не закрыты как контролируемый процесс.

## Приоритизированный backlog gaps

| Приоритет | Gap | Риск для бизнеса | Что нужно закрыть (target state) |
|---|---|---|---|
| **P0** | **SLO/SLA и ownership не закреплены формально** | Невозможно гарантировать предсказуемое качество сервиса | Утвердить SLI/SLO для критичных DAG/витрин, owner по каждому SLO, процедура эскалации |
| **P0** | **Release-gates неполные** | Изменения могут проходить без единых quality gates | Обязательные проверки для релиза: smoke, dbt DQ, health ingress, rollback-checklist |
| **P0** | **Incident response не стандартизирован как процесс** | Высокий MTTR и повторяемость аварий | Единый runbook lifecycle: detect -> triage -> mitigate -> RCA -> preventive actions |
| **P1** | **Security boundary и доступы не закреплены политиками** | Риск несанкционированного доступа к данным/интерфейсам | Trust zones, RBAC/role matrix, секреты вне git, регулярный review доступов |
| **P1** | **Lineage/каталог покрывает не все критичные KPI** | Сложно доказать происхождение цифр для бизнеса/аудита | Для критичных витрин: owner, source, трансформации, дата последнего обновления |
| **P1** | **Data contracts и schema evolution частично ручные** | Регрессии схем и инциденты совместимости | Процедура контрактов и backward-compatibility checks в CI/CD |
| **P2** | **Capacity и performance тестирование нерегулярно** | Неизвестная устойчивость под ростом нагрузки | Нагрузочные сценарии ingestion/serving и пороги деградации |
| **P2** | **DR/backup strategy не оформлена end-to-end** | Длительное восстановление после потери среды | RPO/RTO цели, сценарий восстановления, регулярные учебные восстановления |

## Матрица готовности по доменам

| Домен | Текущий статус | Целевое состояние |
|---|---|---|
| Архитектура | Есть описания компонентов и потоков | Архитектурные решения с ADR и governance циклами |
| Эксплуатация | Есть runbook и мониторинг | Формальные SLO, on-call, postmortem и KPI ops |
| Надёжность | Есть базовые проверки и метрики | Релизные quality gates + регулярные game day |
| Безопасность | Базовая сегментация и ingress | Политики доступа, аудит, секрет-менеджмент, threat model |
| Данные | Есть DQ и Data Vault слой | Data contracts, lineage coverage по критичным KPI |
| Бизнес-управление | Есть use cases и roadmap | KPI ownership, квартальные цели и SLA для потребителей данных |

## Рекомендуемый порядок закрытия (90 дней)

1. **Фаза 1 (0-30 дней):** P0 по SLO, release-gates и incident process.
2. **Фаза 2 (31-60 дней):** P1 по security boundary, доступам и lineage для top KPI.
3. **Фаза 3 (61-90 дней):** P2 по DR/capacity и регулярным reliability-репетициям.

## Связанные документы

- [README.md](README.md)
- [Roadmap.md](Roadmap.md)
- [PIPELINES.md](PIPELINES.md)
- [QUALITY_AND_MONITORING.md](QUALITY_AND_MONITORING.md)
- [runbook/AIRFLOW_DAG_TROUBLESHOOTING.md](runbook/AIRFLOW_DAG_TROUBLESHOOTING.md)
