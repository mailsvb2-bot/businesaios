from __future__ import annotations

import json
import os

from runtime.production_boot_contract import ProductionBootProbe, evaluate_production_boot
from scripts.ci.paths import repo_root


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "production_boot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run() -> tuple[bool, str]:
    proof_env = dict(os.environ)
    proof_env.setdefault("ENV", "ci")
    proof_env.setdefault("APP_PROFILE", "api")
    probe = ProductionBootProbe.from_env(proof_env)
    report = evaluate_production_boot(probe)
    _write_artifact(report)
    if report["production_profile"] is True and report["status"] != "ready":
        return False, "production boot blocked: " + ",".join(report["violations"])
    return True, f"production boot proof artifact written: artifacts/ci/production_boot.json status={report['status']} production_profile={report['production_profile']}"


__all__ = ["run"]
