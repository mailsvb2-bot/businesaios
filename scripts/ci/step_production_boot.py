from __future__ import annotations

import json
import os
from pathlib import Path

from runtime.production_boot_contract import ProductionBootProbe, evaluate_production_boot
from scripts.ci.paths import repo_root

REAL_BOOT_EVIDENCE_NAME = "real_runtime_boot_evidence.json"
CANON_PRODUCTION_BOOT_ENV_DRIFT_GUARD = True
LEGACY_ENV_KEYS = (
    "METRO_DB_ENGINE",
    "STORAGE_DB_ENGINE",
    "METRO_DATABASE_URL",
    "METRO_POSTGRES_DSN",
)


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


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "required", "enabled"}


def _evidence_required() -> bool:
    return _truthy_env("REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED") or _truthy_env("PRODUCTION_BOOT_PROOF_REQUIRED")


def _production_profile_required() -> bool:
    return _truthy_env("PRODUCTION_BOOT_PROOF_REQUIRED")


def _legacy_env_keys_present(env: dict[str, str]) -> list[str]:
    return [name for name in LEGACY_ENV_KEYS if str(env.get(name) or "").strip()]


def _append_violation(report: dict[str, object], *items: str) -> None:
    existing = list(report.get("violations") or [])
    for item in items:
        if item not in existing:
            existing.append(item)
    report["violations"] = existing
    report["status"] = "blocked"
    report["production_boot_contract_satisfied"] = False


def run() -> tuple[bool, str]:
    root = repo_root()
    proof_env = dict(os.environ)
    if _production_profile_required():
        proof_env.setdefault("ENV", "production")
        proof_env.setdefault("APP_ENV", "production")
        proof_env.setdefault("APP_PROFILE", "api")
        proof_env.setdefault("POSTGRES_RUNTIME_ENABLED", "1")
        proof_env.setdefault("POSTGRES_EVENT_STORE_ENABLED", "1")
        proof_env.setdefault("RUN_MIGRATIONS_BEFORE_START", "1")
        proof_env.setdefault("BAIOS_REQUIRE_QUALITY_TOOLS", "release")
    else:
        proof_env.setdefault("ENV", "ci")
        proof_env.setdefault("APP_PROFILE", "api")

    probe = ProductionBootProbe.from_env(proof_env)
    report = evaluate_production_boot(probe)
    report["artifact"] = "production_boot_contract"
    report["proof_kind"] = "contract_aggregation_not_process_boot"
    report["claims_real_runtime_boot"] = False
    report["proof_required"] = _evidence_required()
    legacy_env_keys = _legacy_env_keys_present(proof_env)
    report["legacy_env_keys_present"] = legacy_env_keys
    postgres_report = _read_artifact(root, "postgres_contract.json")
    postgres_migrations = _read_artifact(root, "postgres_migrations.json")
    postgres_live = _read_artifact(root, "postgres_live.json")
    container_runtime = _read_artifact(root, "container_runtime.json")
    real_boot_evidence = _read_artifact(root, REAL_BOOT_EVIDENCE_NAME)
    report["postgres_contract"] = postgres_report
    report["postgres_migrations"] = postgres_migrations
    report["postgres_live"] = postgres_live
    report["container_runtime"] = container_runtime
    report["real_runtime_boot_evidence"] = real_boot_evidence

    if legacy_env_keys:
        _append_violation(report, "legacy_production_env_drift:" + ",".join(legacy_env_keys))

    if _production_profile_required() and report.get("production_profile") is not True:
        _append_violation(report, "production_profile_required")

    if real_boot_evidence.get("status") == "ready":
        report["claims_real_runtime_boot"] = True
        report["real_runtime_boot_evidence_source"] = REAL_BOOT_EVIDENCE_NAME
    elif _evidence_required():
        _append_violation(report, "real_runtime_boot_evidence_required")

    if report.get("production_profile") is True or _production_profile_required():
        extra_violations: list[str] = []
        if postgres_report.get("status") != "ready":
            extra_violations.append("postgres_contract_not_ready")
        if postgres_migrations.get("status") != "ready":
            extra_violations.append("postgres_migrations_not_ready")
        if postgres_live.get("status") != "ready":
            extra_violations.append("postgres_live_not_ready")
        if container_runtime.get("status") != "ready":
            extra_violations.append("container_runtime_not_ready")
        if _evidence_required() and real_boot_evidence.get("status") != "ready":
            extra_violations.append("real_runtime_boot_evidence_not_ready")
        if extra_violations:
            _append_violation(report, *extra_violations)

    _write_artifact(report)
    if report["status"] == "blocked" or (_production_profile_required() and report.get("status") != "contract_satisfied"):
        return False, "production boot contract blocked: " + ",".join(report.get("violations") or [])
    return True, (
        "production boot contract artifact written: artifacts/ci/production_boot.json "
        f"status={report['status']} production_profile={report['production_profile']} "
        f"claims_real_runtime_boot={report['claims_real_runtime_boot']} "
        f"claims_production_ready={report['claims_production_ready']}"
    )


__all__ = ["CANON_PRODUCTION_BOOT_ENV_DRIFT_GUARD", "LEGACY_ENV_KEYS", "_legacy_env_keys_present", "run"]
