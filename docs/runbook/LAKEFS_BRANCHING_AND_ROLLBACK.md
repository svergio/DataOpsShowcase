# lakeFS Branching and Rollback

## Scope
Operational flow for data branching, promotion, and rollback with `infrastructure/lakefs`.

## Start and setup
```bash
make up
make lakefs-setup
```

## Branching model
- `main`: stable branch used by consumer jobs.
- `feature/*`: transient branches for ingestion/transformation experiments.
- `release/*`: optional gate before merge to `main`.

## Typical flow
1. Create branch from `main` for pipeline changes.
2. Run ingestion/transforms to branch path.
3. Validate quality checks and downstream contract tests.
4. Merge branch into `main`.

## Rollback flow
1. Identify last known good commit on `main`.
2. Revert merge commit or reset branch pointer in lakeFS.
3. Re-run impacted downstream jobs using restored snapshot.

## Example commands (lakectl)
```bash
lakectl branch create lakefs://dataops-showcase/feature/load-2026-05 --source lakefs://dataops-showcase/main
lakectl merge lakefs://dataops-showcase/feature/load-2026-05 lakefs://dataops-showcase/main
lakectl log lakefs://dataops-showcase/main --limit 20
```
