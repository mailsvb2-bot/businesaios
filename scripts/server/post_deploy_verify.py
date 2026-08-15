from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.ci.http_probe_io import fetch_json
from scripts.server.smoke_flow import run_smoke_flow

CANON_PRODUCTION_POST_DEPLOY_VERIFIER = True
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_FORBIDDEN_CONTROL_KEYS = {"development-control-plane-key"}
_FORBIDDEN_TENANTS = {"default-business"}


class VerificationError(RuntimeError):
    pass


def _required_env(name: str, *, forbidden: set[str] | None = None) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise VerificationError(f"required production setting is missing: {name}")
    if forbidden and value in forbidden:
        raise VerificationError(f"unsafe production setting for {name}")
    return value


def _expected_sha() -> str:
    value = _required_env("EXPECTED_SHA").lower()
    if not _SHA_RE.fullmatch(value):
        raise VerificationError("EXPECTED_SHA must be a full 40-character git SHA")
    return value


def _database_dsn() -> str:
    value = (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN") or "").strip()
    if not value:
        raise VerificationError("required production PostgreSQL DSN is missing: DATABASE_URL/POSTGRES_DSN")
    return value


def _api_key() -> str:
    return _required_env("CONTROL_PLANE_API_KEY", forbidden=_FORBIDDEN_CONTROL_KEYS)


def _tenant_id() -> str:
    return _required_env("SMOKE_TENANT_ID", forbidden=_FORBIDDEN_TENANTS)


def _require_production_environment() -> str:
    value = _required_env("APP_ENV").lower()
    if value not in {"prod", "production"}:
        raise VerificationError(f"APP_ENV must be prod/production for production verification, got {value!r}")
    return value


def _fetch(path: str, *, api_key: str) -> tuple[int, dict]:
    base = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    return fetch_json(
        f"{base}{path}",
        method="GET",
        headers={"x-api-key": api_key},
        timeout=10,
    )


def _worker_fetch(path: str) -> tuple[int, dict]:
    base = os.getenv("LOCAL_WORKER_BASE", "http://127.0.0.1:8087").rstrip("/")
    return fetch_json(f"{base}{path}", method="GET", timeout=10)


def _observed_sha() -> str:
    deploy_root = Path(os.getenv("BUSINESAIOS_DEPLOY_ROOT", "/opt/businesaios")).resolve()
    if not deploy_root.is_dir():
        raise VerificationError(f"deployment root does not exist: {deploy_root}")
    result = subprocess.run(
        ["git", "-C", str(deploy_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise VerificationError(f"cannot resolve deployed git SHA: {result.stderr.strip()}")
    value = result.stdout.strip().lower()
    if not _SHA_RE.fullmatch(value):
        raise VerificationError(f"invalid deployed git SHA: {value!r}")
    return value


def _check_postgres(dsn: str) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - production dependency guard
        raise VerificationError("psycopg is required for production PostgreSQL verification") from exc
    try:
        with psycopg.connect(dsn, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
    except Exception as exc:
        raise VerificationError(f"PostgreSQL verification failed: {type(exc).__name__}: {exc}") from exc
    if not row or int(row[0]) != 1:
        raise VerificationError(f"PostgreSQL SELECT 1 returned unexpected result: {row!r}")
    return {"select_1": 1}


def _validate_health(status: int, payload: dict) -> dict[str, Any]:
    state = str(payload.get("status") or "").lower()
    if status != 200 or state not in {"ok", "ready"}:
        raise VerificationError(f"health failed: http={status} status={state!r}")
    failed = [item for item in payload.get("checks", []) if item.get("status") != "pass"]
    if failed:
        raise VerificationError(f"health contains failed checks: {failed!r}")
    return {"http_status": status, "status": state, "check_count": len(payload.get("checks", []))}


def _validate_readiness(status: int, payload: dict) -> dict[str, Any]:
    state = str(payload.get("status") or "").lower()
    if status != 200 or state != "ready":
        raise VerificationError(f"readiness failed: http={status} status={state!r}")
    failed = [item for item in payload.get("checks", []) if item.get("status") != "pass"]
    if failed:
        raise VerificationError(f"readiness contains failed checks: {failed!r}")
    return {"http_status": status, "status": state, "check_count": len(payload.get("checks", []))}


def _validate_runtime(health: dict) -> dict[str, Any]:
    details = health.get("details") if isinstance(health.get("details"), dict) else {}
    readiness = details.get("runtime_readiness") or health.get("runtime_readiness")
    if not isinstance(readiness, dict) or readiness.get("ready") is not True:
        raise VerificationError(f"runtime readiness is not true: {readiness!r}")
    orchestrator = health.get("runtime_orchestrator_present")
    if orchestrator is None:
        orchestrator = details.get("runtime_orchestrator_present")
    if orchestrator is not True:
        raise VerificationError("runtime orchestrator is not present")
    worker_status, worker_health = _worker_fetch("/health")
    if worker_status != 200 or worker_health.get("ok") is not True:
        raise VerificationError(f"worker runtime health failed: http={worker_status} payload={worker_health!r}")
    worker_ready_status, worker_ready = _worker_fetch("/ready")
    if worker_ready_status != 200 or worker_ready.get("ok") is not True:
        raise VerificationError(
            f"worker runtime readiness failed: http={worker_ready_status} payload={worker_ready!r}"
        )
    return {
        "runtime_ready": True,
        "runtime_orchestrator_present": True,
        "worker_health": True,
        "worker_ready": True,
    }


def _verdict_path(expected_sha: str) -> Path:
    configured = os.getenv("PRODUCTION_VERDICT_PATH", "").strip()
    if configured:
        return Path(configured)
    root = Path(
        os.getenv(
            "PRODUCTION_VERDICT_DIR",
            "/var/lib/businesaios/runtime/reports/post-deploy",
        )
    )
    return root / f"production-verdict-{expected_sha}.json"


def _write_verdict(path: Path, verdict: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_verification() -> dict[str, Any]:
    expected_sha = _expected_sha()
    environment = _require_production_environment()
    api_key = _api_key()
    tenant_id = _tenant_id()
    dsn = _database_dsn()
    checks: dict[str, Any] = {}
    verdict: dict[str, Any] = {
        "schema_version": 1,
        "verdict": "fail",
        "expected_sha": expected_sha,
        "observed_sha": None,
        "environment": environment,
        "tenant_id": tenant_id,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
    path = _verdict_path(expected_sha)

    def check(name: str, fn: Callable[[], Any]) -> Any:
        try:
            details = fn()
        except Exception as exc:
            checks[name] = {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}
            _write_verdict(path, verdict)
            raise
        checks[name] = {"status": "pass", "details": details}
        return details

    observed_sha = check("deployed_sha", _observed_sha)
    verdict["observed_sha"] = observed_sha
    if observed_sha != expected_sha:
        error = f"observed SHA {observed_sha} does not match expected SHA {expected_sha}"
        checks["sha_match"] = {"status": "fail", "error": error}
        _write_verdict(path, verdict)
        raise VerificationError(error)
    checks["sha_match"] = {"status": "pass", "details": {"sha": expected_sha}}

    health_payload: dict[str, Any] = {}

    def health_check() -> dict[str, Any]:
        status, payload = _fetch("/health", api_key=api_key)
        health_payload.clear()
        health_payload.update(payload)
        return _validate_health(status, payload)

    check("health", health_check)
    check("readiness", lambda: _validate_readiness(*_fetch("/readyz", api_key=api_key)))
    check("runtime", lambda: _validate_runtime(health_payload))
    check("postgresql", lambda: _check_postgres(dsn))
    smoke = check("synthetic_flow", run_smoke_flow)
    verdict["synthetic_run_id"] = smoke["run_id"]
    verdict["verdict"] = "pass"
    verdict["checked_at"] = datetime.now(timezone.utc).isoformat()
    _write_verdict(path, verdict)
    verdict["verdict_path"] = str(path)
    return verdict


def main() -> int:
    try:
        verdict = run_verification()
    except (VerificationError, AssertionError, RuntimeError) as exc:
        print(f"PRODUCTION_POST_DEPLOY_VERIFICATION_FAILED:{exc}", file=sys.stderr)
        return 1
    print(
        "PRODUCTION_POST_DEPLOY_VERIFICATION_PASSED "
        f"sha={verdict['expected_sha']} verdict={verdict['verdict_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
