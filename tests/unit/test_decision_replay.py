"""External decision replay bench tests.

The reward-hacking property under test: a module can emit any event about its
own decisions, but it cannot fool this bench by sealing a flattering outcome
— the bench recomputes the outcome from the sealed inputs and verifies the
quorum from the package alone.
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.core.services.decision_replay import (
    Approval,
    DecisionReplayBench,
    RuleNotRegistered,
    SealedDecisionPackage,
)

T0 = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)


def _rule(inputs: dict):
    """Bench-side decision rule: approved iff amount >= limit."""
    return inputs.get("amount", 0) >= inputs.get("limit", 0)


def _package(**overrides):
    base = dict(
        decision_id="dec-1",
        rule_id="threshold",
        inputs={"amount": 120, "limit": 100},
        sealed_outcome=True,
        approvals=(
            Approval("voter-a", "committee_member", T0),
            Approval("voter-b", "committee_chair", T0 + timedelta(minutes=5)),
        ),
        quorum_required=2,
        required_roles=frozenset({"committee_member", "committee_chair"}),
        sealed_by="sealer-1",
        sealed_at=T0 + timedelta(minutes=30),
    )
    base.update(overrides)
    return SealedDecisionPackage(**base)


@pytest.fixture
def bench():
    b = DecisionReplayBench()
    b.register_rule("threshold", _rule)
    return b


def test_happy_path_passes(bench):
    verdict = bench.evaluate(_package())
    assert verdict.passed
    assert verdict.replay_match
    assert verdict.quorum_ok


def test_replay_detects_inflated_sealed_outcome(bench):
    # the module sealed "approved" but the inputs recompute to "rejected":
    # score inflation is caught independently of any emitted event.
    verdict = bench.evaluate(_package(inputs={"amount": 50, "limit": 100}))
    assert not verdict.passed
    assert not verdict.replay_match
    assert verdict.checks["recomputed_outcome"] is False


def test_quorum_fails_below_required_voters(bench):
    verdict = bench.evaluate(_package(quorum_required=3))
    assert not verdict.passed
    assert verdict.quorum_ok is False
    assert verdict.checks["quorum_distinct_voters"] is False


def test_quorum_fails_on_duplicate_voters(bench):
    verdict = bench.evaluate(_package(approvals=(
        Approval("voter-a", "committee_member", T0),
        Approval("voter-a", "committee_chair", T0 + timedelta(minutes=1)),
    )))
    assert not verdict.checks["quorum_no_duplicate_voters"]
    assert verdict.checks["quorum_distinct_voters"] is False  # 1 < 2


def test_quorum_fails_on_missing_required_role(bench):
    verdict = bench.evaluate(_package(approvals=(
        Approval("voter-a", "committee_member", T0),
        Approval("voter-b", "committee_member", T0 + timedelta(minutes=1)),
    )))
    assert not verdict.checks["quorum_required_roles"]


def test_quorum_fails_when_sealer_is_approver(bench):
    # separation of duties: the sealing identity must not be an approver
    verdict = bench.evaluate(_package(sealed_by="voter-a"))
    assert not verdict.checks["quorum_sealer_not_approver"]


def test_quorum_fails_on_late_approval(bench):
    verdict = bench.evaluate(_package(approvals=(
        Approval("voter-a", "committee_member", T0),
        Approval("voter-b", "committee_chair", T0 + timedelta(hours=1)),
    )))
    assert not verdict.checks["quorum_approvals_before_sealing"]


def test_quorum_fails_without_sealed_at(bench):
    verdict = bench.evaluate(_package(sealed_at=None))
    assert not verdict.checks["quorum_approvals_before_sealing"]


def test_unregistered_rule_fails_closed(bench):
    with pytest.raises(RuleNotRegistered):
        bench.evaluate(_package(rule_id="unknown-rule"))


def test_package_cannot_supply_its_own_rule(bench):
    # registering is a bench-side operation; the package only references a
    # rule_id and gets a closed failure when the bench does not own it.
    assert bench.list_rules() == ["threshold"]
