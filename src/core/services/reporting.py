"""Report generator (ADR-009)."""
import json

from ..domain.test_models import RemediationItem, Report


class ReportGenerator:
    def __init__(self, repository):
        self._repo = repository

    def build_remediations(self, run, results: list) -> list:
        items = []
        for result in results:
            if not result.passed:
                test = self._repo.get_test(result.test_case_id)
                name = test.name if test else result.test_case_id
                items.append(RemediationItem(
                    finding=f"{name} failed",
                    severity="high" if test and test.category == "security" else "medium",
                    action=f"Investigate and fix {name}",
                    test_case_id=result.test_case_id))
        return items

    def generate_json_report(self, run, results: list, scorecard) -> Report:
        remediations = self.build_remediations(run, results)
        payload = {
            "run_id": run.id,
            "target": run.target,
            "status": run.status.value,
            "scorecard": scorecard.to_dict() if scorecard else None,
            "remediations": [r.to_dict() for r in remediations],
        }
        return Report(run_id=run.id, format="json",
                      content=json.dumps(payload, indent=2))

    def generate_html_report(self, run, results: list, scorecard) -> Report:
        remediations = self.build_remediations(run, results)
        rows = "\n".join(
            f"<li><strong>{r.finding}</strong> ({r.severity}): {r.action}</li>"
            for r in remediations
        )
        dimensions = "\n".join(
            f"<li>{k}: {v:.2f}</li>"
            for k, v in (scorecard.dimensions.items() if scorecard else {}.items())
        )
        overall = scorecard.overall if scorecard else 0.0
        html = f"""<!doctype html>
<html><head><title>Bench Report {run.id}</title></head>
<body>
<h1>Arca Bench Report</h1>
<p>Target: {run.target}</p>
<p>Status: {run.status.value}</p>
<p>Overall: {overall:.2f}</p>
<h2>Dimensions</h2>
<ul>{dimensions}</ul>
<h2>Remediations</h2>
<ul>{rows}</ul>
</body></html>"""
        return Report(run_id=run.id, format="html", content=html)

    def generate_report(self, run, results: list, scorecard,
                        format: str = "json") -> Report:
        if format == "html":
            report = self.generate_html_report(run, results, scorecard)
        else:
            report = self.generate_json_report(run, results, scorecard)
        self._repo.save_report(report)
        return report
