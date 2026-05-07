# CI/CD + release governance flow

Диаграмма описывает целевой release-поток для data-platform изменений: код -> quality gates -> controlled rollout -> rollback при необходимости.

## Диаграмма (Mermaid)

```mermaid
flowchart LR
    A[Feature Branch] --> B[Pull Request]
    B --> C[CI: Lint + Unit Tests]
    C --> D[CI: dbt compile/test]
    D --> E{Quality gates passed?}

    E -->|no| F[Fixes in branch]
    F --> B

    E -->|yes| G[Merge to main]
    G --> H[Build/Tag Release Artifact]
    H --> I[Deploy to Staging]
    I --> J[Smoke + DQ + Health checks]
    J --> K{Staging accepted?}

    K -->|no| L[Rollback staging + issue]
    L --> B

    K -->|yes| M[Production rollout window]
    M --> N[Post-release monitoring]
    N --> O{SLO regression?}
    O -->|yes| P[Rollback production]
    O -->|no| Q[Close release]
```

## Практический смысл

- Делает quality gates обязательной частью релиза, а не ручной опцией.
- Увязывает rollout с наблюдаемостью и SLO, чтобы быстро фиксировать регрессы.
- Явно описывает rollback как нормальный путь управления риском.

## См. также

- [../SETUP.md](../SETUP.md)
- [../TESTING_AND_DATA_QUALITY.md](../TESTING_AND_DATA_QUALITY.md)
- [../QUALITY_AND_MONITORING.md](../QUALITY_AND_MONITORING.md)
- [../GAPS_AND_PRODUCTION_READINESS.md](../GAPS_AND_PRODUCTION_READINESS.md)
