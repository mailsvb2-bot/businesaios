from __future__ import annotations

import json
from pathlib import Path

from runtime.production_boot_contract import ProductionBootInput, evaluate_production_boot_contract
from scripts.ci.paths import repo_root


CANON_PRODUCTION_BOOT_PROOF_STEP = True


def _write_artifact(payload: dict[str, object]) -> Path:
    path = repo_root() / "artifacts" / "ci" / "production_boot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def run() -> tuple[bool, str]:
    root = repo_root()
    input_data = ProductionBootInput(
        env="production",
        app_profile="api",
        run_mode="api",
        database_url="postgresql://ci-contract-user:ci-contract-pass@postgres:5432/businesaios",
        postgres_enabled=True,
        migrations_required=True,
        release_id="ci-production-boot-contract",
    )
    report = evaluate_production_boot_contract(input_data)
    artifact = report.to_dict()
    artifact["contract_only"] = True
    artifact["live_database_connection"] = False
    artifact["reason"] = "production boot contract proof without live DB credentials"
    path = _write_artifact(artifact)
    if not report.passed:
        return False, "production boot contract failed"
    rel = path.relative_to(root).as_posix()
    return True, f"production boot contract proof passed: {rel}"


__all__ = ["run"]
