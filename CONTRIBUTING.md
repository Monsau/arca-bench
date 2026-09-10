# Contributing

## Language
All code, comments, documentation and commit messages are written in **English**.

## Architecture Decision Records
Any significant technical decision MUST be recorded as an ADR in `docs/adr/`:

- Numbering: `ADR-NNN-kebab-title.md`, sequential.
- Template: see `docs/adr/ADR-001-bounded-context.md`.
- Status flow: `Proposed` -> `Accepted` / `Rejected` / `Superseded`.
- An ADR that has been materialized in code MUST be updated to `Accepted`
  with a `- Pass N:` line referencing the implementation.

## Ground rules
- Product is autonomous: no direct access to another product's database or code.
- Integration only through contracts: REST/GraphQL, MCP, Kafka events, OOC, evidence.
- Embedded SOC: all five bricks (Collector, Analyzer, Dashboard, Forensics, Responder)
  stay wired via `src/infra/soc.py`.
- No secrets in clear text anywhere (code, manifests, docs).
- No plaintext secrets in Kubernetes manifests; use External Secrets Operator -> Vault.

## Pull requests
- Tests must pass: `python -m pytest -q`.
- Contract changes require an updated ADR and contract tests in `tests/contract/`.
- Never modify another module's contracts without an ADR approved by its CODEOWNERS.
