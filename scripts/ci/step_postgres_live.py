from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

from runtime.platform.postgres_contract import PostgresRuntimeProof, evaluate_postgres_contract
from runtime.platform.postgres_live_probe import PostgresLiveProbeConfig, run_postgres_live_probe
from runtime.platform.postgres_port import PostgresPort
from scripts.ci.paths import repo_root

_BACKUP_EVIDENCE_CONTRACT = "businesaios.postgres_backup_restore_evidence.v1"
_BACKUP_SENTINEL_QUERY = (
    "SELECT commit_sha FROM deep_release_backup_probe.restore_sentinel WHERE id = %s;"
)


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "postgres_live.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "required", "enabled"}


def _dsn() -> str:
    return str(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN") or "").strip()


def _enabled() -> bool:
    return str(os.getenv("POSTGRES_RUNTIME_ENABLED") or os.getenv("POSTGRES_EVENT_STORE_ENABLED") or "").strip().lower() in {"1", "true", "yes", "enabled"}


def _proof_required() -> bool:
    return _truthy_env("POSTGRES_LIVE_PROOF_REQUIRED")


def _apply_migrations() -> bool:
    return str(os.getenv("POSTGRES_APPLY_MIGRATIONS") or os.getenv("RUN_MIGRATIONS_BEFORE_START") or "").strip().lower() in {"1", "true", "yes", "enabled"}


def _expected_commit_sha() -> str:
    return str(os.getenv("GIT_COMMIT_SHA") or os.getenv("BAIOS_CI_TARGET_SHA") or "").strip()


def _is_exact_commit_sha(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def _ci_artifact_file(raw_path: object) -> Path | None:
    value = str(raw_path or "").strip()
    if not value:
        return None
    root = repo_root().resolve()
    artifact_root = (root / "artifacts" / "ci").resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(artifact_root)
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_evidence_status() -> tuple[bool, str]:
    expected_sha = _expected_commit_sha()
    if not expected_sha:
        return False, "postgres_backup_expected_commit_sha_required"
    if not _is_exact_commit_sha(expected_sha):
        return False, "postgres_backup_expected_commit_sha_invalid"

    evidence_path = _ci_artifact_file(os.getenv("POSTGRES_BACKUP_EVIDENCE_PATH"))
    if evidence_path is None:
        return False, "postgres_backup_evidence_path_required"

    restore_dsn = str(os.getenv("POSTGRES_RESTORE_DSN") or "").strip()
    if not restore_dsn:
        return False, "postgres_backup_restore_dsn_required"

    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "postgres_backup_evidence_json_invalid"
    if not isinstance(payload, dict):
        return False, "postgres_backup_evidence_object_required"
    if payload.get("contract") != _BACKUP_EVIDENCE_CONTRACT:
        return False, "postgres_backup_evidence_contract_invalid"
    evidence_sha = str(payload.get("commit_sha") or "").strip()
    if not _is_exact_commit_sha(evidence_sha):
        return False, "postgres_backup_evidence_commit_sha_invalid"
    if evidence_sha != expected_sha:
        return False, "postgres_backup_evidence_commit_sha_mismatch"

    dump_path = _ci_artifact_file(payload.get("dump_path"))
    if dump_path is None:
        return False, "postgres_backup_dump_path_invalid"
    expected_dump_sha256 = str(payload.get("dump_sha256") or "").strip()
    if len(expected_dump_sha256) != 64 or any(char not in "0123456789abcdef" for char in expected_dump_sha256):
        return False, "postgres_backup_dump_sha256_invalid"
    if _sha256(dump_path) != expected_dump_sha256:
        return False, "postgres_backup_dump_sha256_mismatch"

    try:
        with PostgresPort(restore_dsn, application_name="businesaios-postgres-backup-restore-proof") as port:
            row = port.fetchone(_BACKUP_SENTINEL_QUERY, (1,))
    except Exception as exc:
        return False, f"postgres_backup_restore_probe_failed:{type(exc).__name__}"
    restored_sha = str(row[0] if row else "").strip()
    if restored_sha != expected_sha:
        return False, "postgres_backup_restore_commit_sha_mismatch"
    return True, "postgres_backup_restore_verified"


def _block_required_postgres_live(*, dsn: str, enabled: bool, psycopg_available: bool) -> tuple[bool, str]:
    payload = evaluate_postgres_contract(
        PostgresRuntimeProof(
            database_url_present=bool(dsn),
            postgres_enabled=enabled,
            psycopg_available=psycopg_available,
            live_probe_ok=False,
            schema_objects_present=(),
            migrations_applied=(),
            event_store_roundtrip_ok=False,
            outbox_roundtrip_ok=False,
            recovery_contract_ok=False,
        )
    )
    violations = set(payload.get("violations") or ())
    violations.add("postgres_live_real_probe_required")
    if not dsn:
        violations.add("postgres_live_database_url_required")
    if not enabled:
        violations.add("postgres_live_enablement_required")
    if not psycopg_available:
        violations.add("postgres_live_psycopg_required")
    payload["artifact"] = "postgres_live"
    payload["status"] = "blocked"
    payload["violations"] = sorted(violations)
    payload["live_runtime_probe"] = False
    payload["proof_required"] = True
    payload["claims_production_ready"] = False
    _write_artifact(payload)
    return False, "postgres live blocked: " + ",".join(payload["violations"])


def run() -> tuple[bool, str]:
    dsn = _dsn()
    enabled = _enabled()
    required = _proof_required()
    psycopg_available = importlib.util.find_spec("psycopg") is not None
    if not dsn and not enabled:
        if required:
            return _block_required_postgres_live(dsn=dsn, enabled=enabled, psycopg_available=psycopg_available)
        payload = evaluate_postgres_contract(PostgresRuntimeProof.advisory())
        payload["artifact"] = "postgres_live"
        payload["status"] = "advisory_only"
        payload["live_runtime_probe"] = False
        payload["claims_production_ready"] = False
        _write_artifact(payload)
        return True, "postgres live artifact written: artifacts/ci/postgres_live.json status=advisory_only"
    if not dsn or not enabled or not psycopg_available:
        payload = evaluate_postgres_contract(
            PostgresRuntimeProof(
                database_url_present=bool(dsn),
                postgres_enabled=enabled,
                psycopg_available=psycopg_available,
                live_probe_ok=False,
                schema_objects_present=(),
                migrations_applied=(),
                event_store_roundtrip_ok=False,
                outbox_roundtrip_ok=False,
                recovery_contract_ok=False,
            )
        )
        payload["artifact"] = "postgres_live"
        payload["live_runtime_probe"] = False
        payload["proof_required"] = required
        payload["claims_production_ready"] = False
        _write_artifact(payload)
        return False, "postgres live blocked: " + ",".join(payload["violations"])

    backup_evidence_ok, backup_evidence_reason = _backup_evidence_status()
    try:
        payload = run_postgres_live_probe(
            PostgresLiveProbeConfig(
                dsn=dsn,
                apply_migrations=_apply_migrations(),
                proof_id=os.getenv("POSTGRES_LIVE_PROOF_ID", "ci-postgres-live-proof"),
                backup_evidence_ok=backup_evidence_ok,
            )
        )
    except Exception as exc:
        payload = evaluate_postgres_contract(
            PostgresRuntimeProof(
                database_url_present=True,
                postgres_enabled=True,
                psycopg_available=psycopg_available,
                live_probe_ok=False,
                schema_objects_present=(),
                migrations_applied=(),
                event_store_roundtrip_ok=False,
                outbox_roundtrip_ok=False,
                recovery_contract_ok=False,
            )
        )
        payload["artifact"] = "postgres_live"
        payload["live_runtime_probe"] = False
        payload["proof_required"] = required
        payload["backup_evidence_reason"] = backup_evidence_reason
        payload["probe_error"] = f"{type(exc).__name__}: {exc}"
        payload["claims_production_ready"] = False
        _write_artifact(payload)
        return False, "postgres live probe failed: " + str(exc)
    payload["artifact"] = "postgres_live"
    payload["live_runtime_probe"] = True
    payload["proof_required"] = required
    payload["backup_evidence_reason"] = backup_evidence_reason
    payload["claims_production_ready"] = False
    _write_artifact(payload)
    if payload["status"] != "ready":
        return False, "postgres live blocked: " + ",".join(payload["violations"])
    return True, "postgres live ready: artifacts/ci/postgres_live.json"


__all__ = ["run"]
