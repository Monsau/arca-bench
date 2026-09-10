# Incident Runbook — Arca Bench - Test & Evaluation Laboratory

## Severity levels
- SEV1: module down or data corruption in production.
- SEV2: degraded SLO, workaround exists.
- SEV3: cosmetic or internal-only impact.

## Triage checklist
1. Confirm the blast radius (single pod vs whole service) via the SOC Dashboard.
2. Collect correlation IDs from the last 15 minutes (SOCCollector logs/traces).
3. Check recent deployments and config changes; correlate with `git log` and CI.
4. Freeze further deploys until the incident is declared contained.

## Containment
- Scale or restart via the `-k8s` overlays; never edit production manifests by hand.
- Use SOCResponder actions (block/limit/isolate) for abusive actors.
- Escalate with `escalate(incident_id, level)` and open the forensic timeline.

## Communication
- Post in the incident channel; update every 30 minutes for SEV1.
- Record all actions in the incident timeline for the post-mortem.
