from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import sys
import tempfile

from scripts.ci.browser_evidence import BROWSER_EVIDENCE_NAME, BROWSER_EVIDENCE_SCHEMA, browser_artifact_snapshot
from scripts.ci.fs import safe_write_text
from scripts.ci.paths import repo_root, reports_dir
from scripts.ci.subprocess_io import run_command

_RELEASE_GATES = {"release", "pre-release"}
_PRODUCTION_ENV_KEYS = (
    "ENV", "APP_ENV", "APP_PROFILE", "DATABASE_URL", "POSTGRES_DSN", "POSTGRES_RUNTIME_ENABLED",
    "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE", "POSTGRES_APPLY_MIGRATIONS", "RUN_MIGRATIONS_BEFORE_START",
    "BAIOS_REQUIRE_QUALITY_TOOLS",
)


def _write(payload: dict) -> None:
    safe_write_text(reports_dir() / BROWSER_EVIDENCE_NAME, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _runtime_env(*, sha: str | None, runtime_dir: str) -> tuple[dict[str, str], str, str]:
    production = os.environ.get("BAIOS_CI_ACTIVE_GATE", "") in _RELEASE_GATES
    mode, storage = ("production", "postgres") if production else ("development", "isolated-local")
    env = {
        "CI": "1", "BAIOS_CI_TARGET_SHA": sha or "", "BAIOS_E2E_RUNTIME_DIR": runtime_dir,
        "BAIOS_E2E_PYTHON": sys.executable, "BAIOS_E2E_RUNTIME_MODE": mode, "BAIOS_E2E_STORAGE_BACKEND": storage,
    }
    if not production:
        return env, mode, storage
    database_url = str(os.environ.get("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("release browser proof requires DATABASE_URL")
    env.update({key: str(os.environ[key]) for key in _PRODUCTION_ENV_KEYS if str(os.environ.get(key) or "").strip()})
    env.update({
        "ENV": "production", "APP_ENV": "production", "APP_PROFILE": "api",
        "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE": "1",
        "API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS": "0",
        "API_CONTROL_PLANE_API_KEY_PEPPER": secrets.token_urlsafe(48),
        "DECISION_SIGNING_SECRET": secrets.token_urlsafe(64),
        "BUSINESAIOS_API_KEY_STORE_BACKEND": "file",
        "BUSINESAIOS_KEY_PROVIDER_BACKEND": "file",
        "BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64": base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
    })
    return env, mode, storage


def run() -> tuple[bool, str]:
    root, frontend = repo_root(), repo_root() / "frontend"
    sha = os.environ.get("BAIOS_CI_TARGET_SHA") or None
    if shutil.which("npm") is None:
        _write({"schema": BROWSER_EVIDENCE_SCHEMA, "exact_sha": sha, "status": "FAIL", "reason": "npm_missing"})
        return False, "browser-e2e: npm is unavailable"
    browser_dir = root / "artifacts" / "ci" / "browser-e2e"
    shutil.rmtree(browser_dir, ignore_errors=True)
    runtime_dir = tempfile.mkdtemp(prefix="businessaios-browser-e2e-")
    try:
        try:
            runtime_env, mode, storage = _runtime_env(sha=sha, runtime_dir=runtime_dir)
        except RuntimeError as exc:
            _write({"schema": BROWSER_EVIDENCE_SCHEMA, "exact_sha": sha, "status": "FAIL", "reason": str(exc)})
            return False, f"browser-e2e: {exc}"
        outcome = run_command(["npm", "run", "test:e2e"], cwd=frontend, timeout=600, env=runtime_env)
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
    snapshot = browser_artifact_snapshot(browser_dir)
    passed = bool(outcome.returncode == 0 and snapshot)
    _write({
        "schema": BROWSER_EVIDENCE_SCHEMA, "exact_sha": sha,
        "status": "PASS" if passed and sha else "NOT_PROVEN" if passed else "FAIL",
        "runtime_mode": mode, "storage_backend": storage,
        "stats": snapshot["stats"] if snapshot else {}, "projects": snapshot["projects"] if snapshot else [],
        "project_matrix": snapshot["project_matrix"] if snapshot else {}, "artifacts": snapshot["artifacts"] if snapshot else {},
    })
    project_names = [item["name"] for item in snapshot["projects"]] if snapshot else []
    return passed, f"browser-e2e: {'passed' if passed else 'failed'} projects={project_names} mode={mode} storage={storage}; stats={snapshot['stats'] if snapshot else {}}"
