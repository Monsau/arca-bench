"""Skeleton unit tests for arca-bench (pass 1).

Business logic tests land with the implementation passes; the skeleton only
verifies that the SOC bricks expose the required method signatures.
"""
import inspect

from src.infra import soc


def test_soc_bricks_present():
    for cls_name in ("SOCCollector", "SOCAnalyzer", "SOCDashboard",
                     "SOCForensics", "SOCResponder"):
        assert hasattr(soc, cls_name), cls_name


def test_soc_collector_signatures():
    sig = inspect.signature(soc.SOCCollector.collect_event)
    assert list(sig.parameters) == ["self", "event_type", "payload", "correlation_id"]
