"""External decision replay bench (reward-loop breaker).

Purpose (arcaq/arcax reward-hacking analysis, P0): the Suite's modules emit
the audit events that feed their own Trust scores. This bench breaks that
loop for sealed decisions: it takes the *sealed decision package* (the
artifact) as the only input, RE-COMPUTES the outcome from the sealed inputs
with a decision rule registered on the bench side, and verifies the approval
quorum from the package contents alone — never from `flow.*`,
`decision-room.*` or any other event a module emitted about itself.

Trust properties:
- replay_match: recomputed outcome equals the sealed outcome. A module that
  seals a flattering-but-wrong outcome fails here, independently of any
  event it logged.
- quorum_ok: distinct approver count, required roles, no duplicate voters,
  separation of duties (sealer is not an approver), and all approvals
  strictly before the sealing timestamp — all read from the package, not
  from the dashboard's own verdict feed.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass(frozen=True)
class Approval:
    voter_id: str
    role: str
    approved_at: datetime
    approved: bool = True

    def to_dict(self) -> dict:
        return {"voter_id": self.voter_id, "role": self.role,
                "approved_at": self.approved_at.isoformat(),
                "approved": self.approved}


@dataclass(frozen=True)
class SealedDecisionPackage:
    """The sealed artifact under test. Carries everything needed to replay
    and verify the quorum; no external event stream is consulted."""
    decision_id: str
    rule_id: str
    inputs: dict
    sealed_outcome: Any
    approvals: tuple
    quorum_required: int
    required_roles: frozenset = frozenset()
    sealed_by: str = ""
    sealed_at: datetime | None = None
    evidence_hash: str | None = None

    def to_dict(self) -> dict:
        return {"decision_id": self.decision_id, "rule_id": self.rule_id,
                "inputs": self.inputs, "sealed_outcome": self.sealed_outcome,
                "approvals": [a.to_dict() for a in self.approvals],
                "quorum_required": self.quorum_required,
                "required_roles": sorted(self.required_roles),
                "sealed_by": self.sealed_by,
                "sealed_at": self.sealed_at.isoformat() if self.sealed_at else None,
                "evidence_hash": self.evidence_hash}


@dataclass
class ReplayVerdict:
    decision_id: str
    checks: dict = field(default_factory=dict)

    @property
    def replay_match(self) -> bool:
        return self.checks.get("replay_match", False)

    @property
    def quorum_ok(self) -> bool:
        quorum_checks = {k: v for k, v in self.checks.items()
                         if k.startswith("quorum_")}
        return bool(quorum_checks) and all(quorum_checks.values())

    @property
    def passed(self) -> bool:
        return self.replay_match and self.quorum_ok

    def to_dict(self) -> dict:
        return {"decision_id": self.decision_id,
                "passed": self.passed,
                "replay_match": self.replay_match,
                "quorum_ok": self.quorum_ok,
                "checks": self.checks}


class RuleNotRegistered(LookupError):
    pass


class DecisionReplayBench:
    """Holds bench-side decision rules and evaluates sealed packages against
    them. Rules are registered in-process by the bench owner — the package
    under test can never supply its own rule."""

    def __init__(self):
        self._rules: dict[str, Callable[[dict], Any]] = {}

    def register_rule(self, rule_id: str, fn: Callable[[dict], Any]) -> None:
        if not rule_id or fn is None:
            raise ValueError("rule_id and fn are required")
        self._rules[rule_id] = fn

    def list_rules(self) -> list[str]:
        return sorted(self._rules)

    def replay(self, package: SealedDecisionPackage) -> tuple[bool, Any]:
        fn = self._rules.get(package.rule_id)
        if fn is None:
            raise RuleNotRegistered(f"rule {package.rule_id!r} not registered")
        recomputed = fn(dict(package.inputs))
        return recomputed == package.sealed_outcome, recomputed

    def verify_quorum(self, package: SealedDecisionPackage) -> dict:
        """Independent quorum verification from the package artifact only."""
        checks = {}
        positive = [a for a in package.approvals if a.approved]
        voters = {a.voter_id for a in positive}

        checks["quorum_distinct_voters"] = (
            len(voters) >= package.quorum_required,
            f"{len(voters)} distinct approver(s), required "
            f"{package.quorum_required}")

        roles = {a.role for a in positive}
        missing = set(package.required_roles) - roles
        checks["quorum_required_roles"] = (
            not missing, f"missing roles: {sorted(missing) or 'none'}")

        checks["quorum_no_duplicate_voters"] = (
            len(voters) == len(positive),
            f"{len(positive)} approval(s) from {len(voters)} voter(s)")

        checks["quorum_sealer_not_approver"] = (
            package.sealed_by not in voters,
            f"sealed_by={package.sealed_by!r} among approvers: "
            f"{package.sealed_by in voters}")

        if package.sealed_at is not None:
            late = [a.voter_id for a in positive
                    if a.approved_at >= package.sealed_at]
            checks["quorum_approvals_before_sealing"] = (
                not late, f"approvals at/after sealing: {late or 'none'}")
        else:
            checks["quorum_approvals_before_sealing"] = (
                False, "sealed_at missing from package")

        return {k: v[0] for k, v in checks.items()} | {
            "_details": {k: v[1] for k, v in checks.items()}}

    def evaluate(self, package: SealedDecisionPackage) -> ReplayVerdict:
        verdict = ReplayVerdict(decision_id=package.decision_id)
        match, recomputed = self.replay(package)
        verdict.checks["replay_match"] = match
        verdict.checks["recomputed_outcome"] = recomputed
        quorum = self.verify_quorum(package)
        details = quorum.pop("_details", {})
        verdict.checks.update(quorum)
        verdict.checks["_details"] = details
        return verdict
