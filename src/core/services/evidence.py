"""Evidence collector (ADR-009)."""
import hashlib

from ..domain.test_models import Evidence


class EvidenceCollector:
    def __init__(self, repository):
        self._repo = repository

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def collect_evidence(self, run_id: str, artifact_url: str,
                         content: bytes | None = None) -> Evidence:
        sha256 = self.compute_sha256(content) if content else ""
        evidence = Evidence(run_id=run_id, artifact_url=artifact_url,
                            sha256=sha256)
        self._repo.save_evidence(evidence)
        return evidence

    def list_evidence(self, run_id: str) -> list:
        return self._repo.get_evidence(run_id)
