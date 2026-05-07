# ArgoCD Promotion Flow

## Scope
Promotion model for GitOps delivery using manifests in `infrastructure/argocd`.

## Environments
- `dataops-dev` tracks `develop` branch.
- `dataops-prod` tracks `main` branch with manual promotion gate.

## Bootstrap
```bash
make up
```

Then apply project/apps in target Kubernetes cluster:
```bash
kubectl apply -f infrastructure/argocd/projects/dataops-platform-project.yaml
kubectl apply -f infrastructure/argocd/apps/dataops-dev.yaml
kubectl apply -f infrastructure/argocd/apps/dataops-prod.yaml
```

## Promotion flow
1. Merge feature PR into `develop`.
2. ArgoCD syncs `dataops-dev` automatically.
3. Validate smoke checks, data quality checks, and dashboard status.
4. Promote to `main` via release PR.
5. Run controlled sync for prod:
   ```bash
   make gitops-sync
   ```

## Rollback
- Revert release commit in Git.
- Sync target app again (`make gitops-sync` with `dataops-prod` argument).
