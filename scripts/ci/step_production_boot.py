from __future__ import annotations

import json
import os
from pathlib import Path

from runtime.production_boot_contract import ProductionBootProbe, evaluate_production_boot
from scripts.ci.paths import repo_root


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "production_boot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read_postgres_contract(root: Path) -> dict[str, object]:
    path = root / "artifacts" / "ci" / "postgres_contract.json"
    if not path.exists():
        return {"artifact": "postgres_contract", "status": "missing", "violations": ["postgres_contract_artifact_missing"]}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"artifact": "postgres_contract", "status": "invalid", "violations": ["postgres_contract_artifact_invalid"]}
    return dict(payload)


def run() -> tuple[bool, str]:
    root = repo_root()
    proof_env = dict(os.environ)
    proof_env.setdefault("ENV", "ci")
    proof_env.setdefault("APP_PROFILE", "api")
    probe = ProductionBootProbe.from_env(proof_env)
    report = evaluate_production_boot(probe)
    postgres_report = _read_postgres_contract(root)
    report["postgres_contract"] = postgres_report
    if report["production_profile"] is True and postgres_report.get("status") != "ready":
        report.setdefault("violations", [])
        violations = list(report["violations"])
        violations.append("postgres_contract_not_ready")
        report["violations"] = violations
        report["status"] = "blocked"
        report["production_boot_contract_satisfied"] = False
    _write_artifact(report)
    if report["production_profile"] is True and report["status"] == "blocked":
        return False, "production boot blocked: " + ",".join(report["violations"])
    return True, (
        "production boot proof artifact written: artifacts/ci/production_boot.json "
        f"status={report['status']} production_profile={report['production_profile']} "
        f"claims_production_ready={report['claims_production_ready']}"
    )


__all__ = ["run"]