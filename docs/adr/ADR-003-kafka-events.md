# ADR-003: Kafka Events

- Status: Accepted
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
Run and score events feed downstream trust and certification.

## Decision
All asynchronous integration uses Kafka with Avro schemas versioned in `contracts/kafka/`. Topics are owned by this module; consumers replay from the log.
- Pass 2: materialized in code (domain, service, SQL repository, REST and MCP handlers).

## Consequences
Loose coupling and replayability; schema evolution governed by compatibility rules.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
