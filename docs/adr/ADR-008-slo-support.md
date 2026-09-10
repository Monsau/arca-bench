# ADR-008: SLO & Support

- Status: Proposed
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
CI and cockpit calls need low-latency catalog reads.

## Decision
Availability SLO 99.5%, p95 catalog read < 200 ms. Alerts: run failure rate > 10%, score computation mismatch, runner unavailable (SEV1).

## Consequences
SLOs are measured on the module's own SLIs; alerting routes to the embedded SOC Responder and to the on-call runbook.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
