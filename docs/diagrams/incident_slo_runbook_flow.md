# Incident + SLO + Runbook flow

Диаграмма показывает целевой operational lifecycle: от срабатывания алерта до RCA и обновления runbook/SLO.

## Диаграмма (Mermaid)

```mermaid
flowchart TD
    A[Pipeline/Service Metrics] --> B[Prometheus Alert Rules]
    B --> C{Alert Severity}

    C -->|warning| D[On-duty Engineer Triage]
    C -->|critical| E[Immediate Incident Channel]

    D --> F{SLO breached?}
    E --> F

    F -->|no| G[Create ticket, monitor trend]
    F -->|yes| H[Runbook-driven Mitigation]

    H --> I{Mitigation successful?}
    I -->|yes| J[Service restored]
    I -->|no| K[Escalate to Platform Lead]
    K --> L[Fallback or Rollback]
    L --> J

    J --> M[Postmortem / RCA]
    M --> N[Action Items with owners]
    N --> O[Update alerts and runbook]
    O --> P[Revisit SLO thresholds]
```

## Практический смысл

- Разделяет warning и critical путь эскалации.
- Привязывает инцидент к SLO-контексту, а не только к факту ошибки.
- Закрывает цикл обучения: RCA -> actions -> обновление правил/документации.

## См. также

- [../runbook/AIRFLOW_DAG_TROUBLESHOOTING.md](../runbook/AIRFLOW_DAG_TROUBLESHOOTING.md)
- [../OBSERVABILITY_AND_LOGGING.md](../OBSERVABILITY_AND_LOGGING.md)
- [../GAPS_AND_PRODUCTION_READINESS.md](../GAPS_AND_PRODUCTION_READINESS.md)
