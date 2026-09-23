"""OPA/Rego policy runner for arca-bench (ADR-009).

``src/policies/bench.rego`` is the policy-as-code contract for the bench.
The enforcement path remains the Python stack (RBAC + ABAC in
``src/core/security/jwt.py`` and ``src/policies/``); this module executes
``bench.rego`` through an OPA binary **when one is available** so the Rego
contract is validated against the same inputs. When no OPA runner exists,
the Rego file is strictly informative and a single clear log line says so —
no silent pretending, and no new dependencies (stdlib ``subprocess`` only).
"""
import json
import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

REGO_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "policies", "bench.rego")


def find_opa_runner() -> str | None:
    """Locate an OPA executable: PATH first, then the active venv."""
    runner = shutil.which("opa")
    if runner:
        return runner
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        for candidate in (os.path.join(venv, "Scripts", "opa.exe"),
                          os.path.join(venv, "bin", "opa")):
            if os.path.isfile(candidate):
                return candidate
    return None


def evaluate_policy(input_data: dict, runner: str | None = None) -> dict:
    """Evaluate bench.rego through OPA.

    Returns {"evaluated": True, "result": <opa 'allow' value>} when a runner
    produced a verdict, otherwise {"evaluated": False, "reason": <message>}.
    Never raises for missing runners or OPA errors — the Rego contract is
    informative unless a runner is present.
    """
    runner = runner or find_opa_runner()
    if not runner:
        return {"evaluated": False,
                "reason": "no OPA runner found (looked on PATH and in the venv)"}
    try:
        proc = subprocess.run(
            [runner, "eval", "--format", "json", "--data", REGO_PATH,
             "--input", "/dev/stdin", "data.arca.bench.allow"],
            input=json.dumps(input_data), capture_output=True, text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("OPA evaluation failed: %s", exc)
        return {"evaluated": False, "reason": f"opa execution failed: {exc}"}
    if proc.returncode != 0:
        logger.warning("OPA evaluation error: %s", proc.stderr.strip())
        return {"evaluated": False,
                "reason": f"opa exited {proc.returncode}: {proc.stderr.strip()}"}
    try:
        verdict = json.loads(proc.stdout)["result"][0]["expressions"][0]["value"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("OPA output unparsable: %s", exc)
        return {"evaluated": False, "reason": f"unparsable opa output: {exc}"}
    return {"evaluated": True, "result": verdict}


def log_policy_mode() -> None:
    """Startup log line: state clearly whether bench.rego is enforced by an
    OPA runner or is strictly informative."""
    runner = find_opa_runner()
    if runner:
        probe = evaluate_policy(
            {"user": {"roles": ["bench_reader"], "allowed_targets": None},
             "permission": "read"},
            runner=runner)
        logger.info("OPA runner found at %s; bench.rego evaluated at startup: %s",
                    runner, probe)
    else:
        logger.info(
            "No OPA runner found: src/policies/bench.rego is strictly "
            "informative (policy-as-code contract); enforcement is provided "
            "by the Python RBAC/ABAC stack.")
