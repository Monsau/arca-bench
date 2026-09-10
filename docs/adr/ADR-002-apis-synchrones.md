# ADR-002: Synchronous APIs (REST/GraphQL)

- Status: Accepted
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
Consumers need synchronous access to the catalog, runs and scores.

## Decision
Expose the synchronous contract through REST (OpenAPI 3.1) and GraphQL (SDL). Rate limiting and OIDC are enforced at the gateway and at handler level.
- Pass 2: materialized in code (domain, service, SQL repository, REST and MCP handlers).

## Consequences
Consumers depend only on `contracts/rest/` and `contracts/graphql/`; internal models stay private.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
