# ADR-005: Store & Retention

- Status: Accepted
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
Raw test outputs can be large but are not long-term evidence.

## Decision
PostgreSQL 16, RPO 5 minutes. Raw logs retained 90 days; score records and run summaries retained 3 years. AES-256 at rest.
- Pass 2: materialized in code (domain, service, SQL repository, REST and MCP handlers).

## Consequences
The store is private to this module; backups, encryption and retention follow `docs/data-governance.md`.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
