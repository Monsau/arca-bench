# ADR-004: MCP Capabilities

- Status: Accepted
- Date: 2026-09-05
- Owners: see CODEOWNERS

## Context
Agents and CI pipelines trigger runs through MCP capabilities.

## Decision
Agent-facing capabilities are exposed via MCP, declared in `contracts/mcp/capabilities.json`, and published only after OOC gates pass.
- Pass 2: materialized in code (domain, service, SQL repository, REST and MCP handlers).

## Consequences
Agents integrate through contracts only; no direct store or code sharing.

## Compliance
- Product autonomy: this module never reads another module's store directly.
- Integration happens only through published contracts (REST/GraphQL, MCP, Kafka, OOC, evidence).
- Embedded SOC bricks stay wired; OIDC, policies, telemetry and audit are never bypassed.
