# Arca Bench V2.3 — Test & Evaluation Laboratory

## Purpose
Arca Bench is the Arca Suite module that measures the quality, performance, resilience and conformance of assets produced by other modules. It owns the test catalogue, the runner engine, the scoring engine, the evidence collector and the report generator. Its outputs (scores, scorecards, evidence bundles and remediation reports) are consumed by Arca Trust and Arca Cert through published contracts only.

## Scope
- **Test Registry**: versioned, categorized catalogue of reusable test cases.
- **Test Runner Engine**: executes suites against a target, records per-test results and run status.
- **Scoring Engine**: computes dimension scores and an overall scorecard from test results.
- **Evidence Collector**: collects and hashes evidence artifacts associated with a run.
- **Report Generator**: produces HTML/JSON remediation reports from completed runs.
- **External Decision Replay** (reward-loop breaker): re-computes sealed outcomes from the sealed decision package with bench-side rules and verifies the approval quorum from the package contents only — never from module-emitted events. Exposed via `POST /api/v1/decision-replay/evaluate`.
- **Integration surfaces**: REST, GraphQL, MCP tools and Kafka events.

## Autonomy
Arca Bench does not import business code from other Arca modules and does not access their databases. Integration happens exclusively through:
- synchronous contracts: REST (`contracts/rest/openapi.yaml`) and GraphQL (`contracts/graphql/schema.graphql`)
- agent capabilities: MCP (`contracts/mcp/capabilities.json`)
- asynchronous events: Kafka with Avro schemas (`contracts/kafka/events.avsc`)
- governance: Operational Ontology Contracts (OOC) and evidence bundles

## Embedded SOC
Every operation that changes state is collected by the embedded SOC (`src/infra/soc.py`): Collector, Analyzer, Dashboard, Forensics, Responder. There is no bypass.

## Security
- Authentication: OIDC / JWT bearer tokens verified against a configurable JWKS endpoint.
- Authorization: RBAC (`bench_admin`, `bench_runner`, `bench_reader`) and ABAC checks based on token claims, target and action.

## Entry points
- REST: `http://localhost:8092/api/v1`
- GraphQL: `http://localhost:8092/graphql`
- MCP: `http://localhost:8092/mcp`
- UI: `http://localhost:8092/ui/`
- Health: `http://localhost:8092/healthz`

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
uvicorn src.main:app --host 0.0.0.0 --port 8092
curl http://localhost:8092/healthz
```
