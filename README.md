# Arca Bench - Test & Evaluation Laboratory

## Mission
Arca Bench executes reproducible test suites against Arca Suite assets. It owns the test registry, the runner engine, the scoring logic and the evidence collector that feeds Arca Trust and Arca Cert.

## Status
Scaffolding (pass 1). Skeleton code compiles and exposes a health endpoint;
business logic is intentionally not implemented yet.

## Autonomy
This repository is an autonomous product. It does not depend on the code or the
database of any other Arca Suite module. Integration with other modules happens
exclusively through contracts:

- Synchronous APIs: REST and GraphQL (`contracts/rest/`, `contracts/graphql/`)
- Agent capabilities: MCP (`contracts/mcp/`)
- Asynchronous events: Kafka with Avro schemas (`contracts/kafka/`)
- Governance: Operational Ontology Contracts (OOC) and evidence bundles

## Embedded SOC
The module embeds its five security bricks in `src/infra/soc.py`:
Collector, Analyzer, Dashboard, Forensics, Responder. No bypass is allowed.

## Layout
See the standard layout documented in CONTRIBUTING.md:
`src/` (api, core, infra, policies), `tests/`, `contracts/`, `docs/`, `scripts/`.

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
uvicorn src.main:app --host 0.0.0.0 --port 8092
curl http://localhost:8092/healthz
```

## Dependencies
None at code level (autonomous product). Contract-level consumers: arca-trust (score and certification evidence), arca-cert (dossier inputs), arca-exchange (test-marketplace compatibility).

## Operations
- Runbooks: `docs/runbooks/`
- ADRs: `docs/adr/`
- Data governance: `docs/data-governance.md`
- Kubernetes manifests: sibling repository `arca-bench-k8s`
