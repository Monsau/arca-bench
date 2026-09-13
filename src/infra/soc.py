"""Embedded SOC: the five mandatory bricks. No telemetry or audit bypass allowed (ADR-009)."""
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum


class IncidentStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    ESCALATED = "escalated"


class SOCCollector:
    def __init__(self):
        self._events: list = []
        self._logs: list = []
        self._traces: list = []
        self._metrics: list = []

    def collect_event(self, event_type: str, payload: dict,
                      correlation_id: str):
        self._events.append({
            "type": event_type,
            "payload": payload,
            "correlation_id": correlation_id,
            "timestamp": _now().isoformat(),
        })

    def collect_log(self, level: str, message: str, context: dict):
        self._logs.append({
            "level": level,
            "message": message,
            "context": context,
            "timestamp": _now().isoformat(),
        })

    def collect_trace(self, span_name: str, attributes: dict):
        self._traces.append({
            "span": span_name,
            "attributes": attributes,
            "timestamp": _now().isoformat(),
        })

    def collect_metric(self, name: str, value: float, labels: dict):
        self._metrics.append({
            "name": name,
            "value": value,
            "labels": labels,
            "timestamp": _now().isoformat(),
        })

    def events(self) -> list:
        return list(self._events)

    def logs(self) -> list:
        return list(self._logs)


class SOCAnalyzer:
    def __init__(self, collector: SOCCollector):
        self._collector = collector

    def detect_anomaly(self, signal_type: str, threshold: float) -> list:
        anomalies = []
        if signal_type == "run_failure_rate":
            recent = [e for e in self._collector.events()
                      if e["type"] == "run_completed"]
            if recent:
                failed = sum(1 for e in recent
                             if e["payload"].get("status") == "failed")
                rate = failed / len(recent)
                if rate > threshold:
                    anomalies.append({
                        "signal": signal_type,
                        "rate": rate,
                        "threshold": threshold,
                        "severity": "high",
                    })
        return anomalies

    def evaluate_risk(self, event_stream: list) -> dict:
        failed = sum(1 for e in event_stream
                     if e.get("payload", {}).get("status") == "failed")
        return {"failed_count": failed, "risk_level": "high" if failed else "low"}


class SOCDashboard:
    def __init__(self, collector: SOCCollector, analyzer: SOCAnalyzer):
        self._collector = collector
        self._analyzer = analyzer

    def health_status(self) -> dict:
        return {"status": "ok", "events_collected": len(self._collector.events())}

    def risk_summary(self) -> dict:
        anomalies = self._analyzer.detect_anomaly("run_failure_rate", 0.1)
        return {"anomalies": anomalies, "risk_level": anomalies[0]["severity"] if anomalies else "low"}

    def incident_list(self, status: str = None) -> list:
        incidents = [e for e in self._collector.events()
                     if e["type"].startswith("incident_")]
        if status:
            incidents = [i for i in incidents
                         if i["payload"].get("status") == status]
        return incidents


class SOCForensics:
    def __init__(self, collector: SOCCollector):
        self._collector = collector

    def reconstruct_timeline(self, correlation_id: str) -> list:
        return [e for e in self._collector.events()
                if e["correlation_id"] == correlation_id]

    def audit_trail(self, entity_type: str, entity_id: str) -> list:
        return [e for e in self._collector.events()
                if e["payload"].get("entity_type") == entity_type
                and e["payload"].get("entity_id") == entity_id]


class SOCResponder:
    def __init__(self, collector: SOCCollector):
        self._collector = collector
        self._actions: list = []

    def _record(self, action: str, target: str, reason: str):
        entry = {"action": action, "target": target,
                 "reason": reason, "timestamp": _now().isoformat()}
        self._actions.append(entry)
        self._collector.collect_event(
            "incident_response", entry, correlation_id=target)
        return True

    def block(self, target: str, reason: str) -> bool:
        return self._record("block", target, reason)

    def limit(self, target: str, rate: int) -> bool:
        return self._record("limit", target, f"rate={rate}")

    def isolate(self, target: str) -> bool:
        return self._record("isolate", target, "security isolation")

    def revoke(self, credential_id: str) -> bool:
        return self._record("revoke", credential_id, "credential revoked")

    def rollback(self, deployment_id: str) -> bool:
        return self._record("rollback", deployment_id, "rollback executed")

    def escalate(self, incident_id: str, level: str) -> bool:
        return self._record("escalate", incident_id, f"level={level}")


class EmbeddedSOC:
    def __init__(self):
        self.collector = SOCCollector()
        self.analyzer = SOCAnalyzer(self.collector)
        self.dashboard = SOCDashboard(self.collector, self.analyzer)
        self.forensics = SOCForensics(self.collector)
        self.responder = SOCResponder(self.collector)


@contextmanager
def audit_operation(soc: EmbeddedSOC, operation: str, correlation_id: str,
                    entity_type: str = None, entity_id: str = None,
                    user: dict = None):
    payload = {"operation": operation, "entity_type": entity_type,
               "entity_id": entity_id, "user": user}
    soc.collector.collect_event("operation_started", payload, correlation_id)
    soc.collector.collect_trace(operation, {"correlation_id": correlation_id})
    try:
        yield soc
        soc.collector.collect_event("operation_succeeded", payload,
                                    correlation_id)
    except Exception as exc:
        soc.collector.collect_event("operation_failed", {
            **payload, "error": str(exc)}, correlation_id)
        soc.collector.collect_log("error", str(exc), {
            "operation": operation, "correlation_id": correlation_id})
        raise


def _now():
    return datetime.now(timezone.utc)
