# ADR-001: Bounded Context & Ownership

- Status: Accepted
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
Arca Bench owns the test lifecycle. Bounded context aggregates: TestCase (catalog entry), TestRun (aggregate root), TestResult and Score.

## Decision
TestCase, TestRun, TestResult and Score are owned here. Results are reproducible: each run pins the test-case version and target version.
- Pass 2: materialized in code (domain, service, SQL repository, REST and MCP handlers).

## Consequences
The bounded context is owned by this repo's CODEOWNERS; aggregates can only be modified through this module's APIs and events.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
