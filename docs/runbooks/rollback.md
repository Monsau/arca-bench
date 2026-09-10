# Rollback Runbook — Arca Bench - Test & Evaluation Laboratory

1. Identify the last known-good deployment revision from the delivery pipeline.
2. Apply the previous overlay: `kubectl apply -k overlays/prod` at the pinned revision.
3. Verify `/healthz` and `/readyz` on all pods before resuming traffic.
4. Run the contract smoke tests in `tests/contract/`.
5. If data migrations are involved, restore from backup per `docs/data-governance.md`.
6. Declare rollback complete only when SLOs are green for 15 minutes.
