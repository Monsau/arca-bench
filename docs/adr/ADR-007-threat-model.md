# ADR-007: Threat Model

- Status: Proposed
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
Scores drive certification; tampering with results is critical.

## Decision
STRIDE analysis per component: spoofing countered by OIDC/mTLS, tampering by signed events and immutable audit, repudiation by the decision ledger, information disclosure by encryption and minimization, DoS by rate limiting and KEDA, elevation of privilege by RBAC/ABAC and least privilege.

## Consequences
Residual risks tracked in `docs/runbooks/`; blast radius limited by autonomy.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
