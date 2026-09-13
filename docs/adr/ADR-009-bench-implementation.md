# ADR-009: Arca Bench V2.3 Implementation

- Status: Accepted
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
`arca-bench` reached scaffolding completeness in pass 1. The module needed real business logic, security, integration interfaces and a UI to become a usable Arca Suite V2.3 component while preserving autonomy.

## Decision
1. Split business logic into focused services:
   - `TestRegistry` for the catalogue
   - `TestRunnerEngine` for execution
   - `ScoringEngine` for dimension/overall scores
   - `EvidenceCollector` for artifact collection
   - `ReportGenerator` for remediation reports
   A thin `BenchService` facade orchestrates them and publishes domain events.
2. Extend the domain model with `Evidence`, `Scorecard`, `RemediationItem` and `Report`.
3. Wire every mutation through the embedded SOC (`src/infra/soc.py`) using `audit_operation` and `collect_event`.
4. Implement OIDC/JWT auth with RBAC/ABAC policies; protect write endpoints.
5. Provide REST, GraphQL (Strawberry) and MCP interfaces with real resolvers and tools (`run_test_suite`, `get_scorecard`, `generate_report`).
6. Add an `aiokafka`-based consumer for `asset.published` events that triggers a default suite.
7. Serve a static dashboard UI under `/ui/`.
8. Update all contracts (OpenAPI, GraphQL, MCP JSON, Avro schemas).

## Consequences
- The module is now fully functional and testable end-to-end.
- Autonomy is preserved: all cross-module integration goes through contracts.
- Security cannot be bypassed; auth is configurable for development/tests.
- Kafka consumer degrades gracefully when Kafka is unavailable.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
