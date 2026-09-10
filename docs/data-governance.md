# Data Governance — Arca Bench - Test & Evaluation Laboratory

## Classification
Test cases and scores: Internal. Raw logs may contain tenant metadata: Confidential. No personal data is stored in this module.

## Retention
Raw run logs: 90 days. Run summaries and scores: 3 years. Test-case versions: retained indefinitely.

## Jurisdiction
Data residency follows the deployed Country Pack sovereignty rules; cross-border
transfers require an explicit governance decision recorded as an ADR.

## Encryption
- At rest: AES-256 (managed keys via Vault/ESO).
- In transit: mTLS STRICT inside the mesh (PeerAuthentication), TLS 1.3 at the edge.

## Secrets
No secret in clear text in code, manifests or docs. Runtime secrets come from
Vault through the External Secrets Operator.
