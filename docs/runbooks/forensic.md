# Forensic Runbook — Arca Bench - Test & Evaluation Laboratory

1. Secure evidence first: export logs, traces and the audit trail before any restart.
2. Use `SOCForensics.reconstruct_timeline(correlation_id)` to rebuild the event sequence.
3. Use `SOCForensics.audit_trail(entity_type, entity_id)` for entity-scoped history.
4. Preserve hashes of evidence bundles; chain of custody is mandatory for regulators.
5. Write the post-mortem within 5 business days, linked from the incident record.
