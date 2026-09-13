# Arca Bench - Test & Evaluation Laboratory

## Mission
Arca Bench executes reproducible test suites against Arca Suite assets. It owns the test registry, the runner engine, the scoring logic, the evidence collector and the report generator that feed Arca Trust and Arca Cert.

## Status
Implemented (V2.3). Business logic, authenticated APIs, embedded SOC, dashboard UI and Kafka integration are in place.

## Autonomy
This repository is an autonomous product. It does not depend on the code or the database of any other Arca Suite module. Integration with other modules happens exclusively through contracts:

- Synchronous APIs: REST and GraphQL (`contracts/rest/`, `contracts/graphql/`)
- Agent capabilities: MCP (`contracts/mcp/`)
- Asynchronous events: Kafka with Avro schemas (`contracts/kafka/`)
- Governance: Operational Ontology Contracts (OOC) and evidence bundles

## Embedded SOC
The module embeds its five security bricks in `src/infra/soc.py`: Collector, Analyzer, Dashboard, Forensics, Responder. No bypass is allowed; every state-changing operation is audited.

## Security
- Authentication: OIDC / JWT bearer tokens verified against a configurable JWKS endpoint or a dev shared secret.
- Authorization: RBAC (`bench_admin`, `bench_runner`, `bench_reader`) and ABAC checks in `src/policies/`.

## Capabilities
- Register and version test cases.
- Start test runs and submit results.
- Compute dimension scores and overall scorecards.
- Collect evidence artifacts with SHA-256 hashes.
- Generate JSON/HTML remediation reports.
- Trigger runs on `asset.published` Kafka events.
- Expose REST, GraphQL and MCP interfaces.
- Serve a minimal dashboard at `/ui/`.

## Layout
See the standard layout documented in `CONTRIBUTING.md`: `src/` (api, core, infra, policies), `tests/`, `contracts/`, `docs/`, `scripts/`.

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
uvicorn src.main:app --host 0.0.0.0 --port 8092
curl http://localhost:8092/healthz
curl http://localhost:8092/ui/
```

## Configuration
| Variable | Description |
|----------|-------------|
| `BENCH_OIDC_JWKS_URL` | OIDC JWKS URL for JWT verification |
| `BENCH_JWT_SECRET` | Shared secret for HS256 dev tokens |
| `BENCH_AUTH_DISABLED` | Set to `1` to disable auth (tests only) |
| `BENCH_DEFAULT_SUITE` | Comma-separated test IDs triggered by `asset.published` |
| `BENCH_KAFKA_BOOTSTRAP_SERVERS` | Kafka bootstrap servers |

## Dependencies
None at code level (autonomous product). Contract-level consumers: arca-trust (score and certification evidence), arca-cert (dossier inputs), arca-exchange (test-marketplace compatibility).

## Operations
- Runbooks: `docs/runbooks/`
- ADRs: `docs/adr/`
- Data governance: `docs/data-governance.md`
- Kubernetes manifests: sibling repository `arca-bench-k8s`
