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


def _read_artifact(root: Path, name: str) -> dict[str, object]:
    path = root / "artifacts" / "ci" / name
    artifact_name = name.removesuffix(".json")
    if not path.exists():
        return {"artifact": artifact_name, "status": "missing", "violations": [f"{artifact_name}_artifact_missing"]}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"artifact": artifact_name, "status": "invalid", "violations": [f"{artifact_name}_artifact_invalid"]}
    return dict(payload)


def run() -> tuple[bool, str]:
    root = repo_root()
    proof_env = dict(os.environ)
    proof_env.setdefault("ENV", "ci")
    proof_env.setdefault("APP_PROFILE", "api")
    probe = ProductionBootProbe.from_env(proof_env)
    report = evaluate_production_boot(probe)
    postgres_report = _read_artifact(root, "postgres_contract.json")
    postgres_live = _read_artifact(root, "postgres_live.json")
    report["postgres_contract"] = postgres_report
    report["postgres_live"] = postgres_live
    if report["production_profile"] is True:
        extra_violations: list[str] = []
        if postgres_report.get("status") != "ready":
            extra_violations.append("postgres_contract_not_ready")
        if postgres_live.get("status") != "ready":
            extra_violations.append("postgres_live_not_ready")
        if extra_violations:
            report.setdefault("violations", [])
            violations = list(report["violations"])
            violations.extend(extra_violations)
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