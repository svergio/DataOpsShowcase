# Security boundaries and trust zones

Диаграмма фиксирует целевую модель зон доверия и каналов доступа для платформы. Это ориентир для hardening, а не утверждение полной реализации.

## Диаграмма (Mermaid)

```mermaid
flowchart TB
    U[Users: Analysts / Engineers] --> I[Ingress Zone]
    I --> P[Portal and Web UIs]

    subgraph Z1[Zone 1: Edge / Ingress]
      I
      P
    end

    subgraph Z2[Zone 2: Orchestration and Control Plane]
      A[Airflow]
      D[dbt REST]
      G[Grafana/Prometheus]
    end

    subgraph Z3[Zone 3: Data Plane]
      K[Kafka]
      M[MinIO]
      O[Postgres OLTP/OLAP]
      S[Spark]
    end

    subgraph Z4[Zone 4: Metadata and Governance]
      T[Atlas/Lineage]
      R[Meta schema]
    end

    I --> A
    I --> D
    I --> G
    A --> S
    S --> O
    K --> S
    M --> S
    O --> R
    A --> T

    X[Secrets and Configs] -. scoped access .-> Z2
    X -. scoped access .-> Z3
```

## Практический смысл

- Отделяет публичный ingress-периметр от внутренних контуров обработки данных.
- Подчёркивает необходимость role-based доступа и scoped secrets по зонам.
- Помогает обсуждать threat model и hardening без привязки к конкретному облаку.

## См. также

- [c4-container.md](c4-container.md)
- [../ARCHITECTURE.md](../ARCHITECTURE.md)
- [../GAPS_AND_PRODUCTION_READINESS.md](../GAPS_AND_PRODUCTION_READINESS.md)
