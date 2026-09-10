# ADR-006: KEDA Triggers

- Status: Proposed
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
Test runs are bursty and queue-driven.

## Decision
Horizontal scaling is event-driven via KEDA scaled objects on the module's Kafka consumer lag, with HPA as fallback. See the `-k8s` repository.

## Consequences
Scale-to-zero on quiet periods; thresholds tuned per environment in overlays.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
