from __future__ import annotations

import shutil
from contextlib import suppress
from pathlib import Path

from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_command

_RUNTIME_STATE_PATTERNS = ("*.sqlite3", "*.sqlite", "*.db")
_RUNTIME_STATE_ROOTS = (
    ".runtime",
    "data/runtime",
    "data/config",
    "data/tenancy",
)
_CI_DEMO_STATE_ROOT = Path("/tmp/businesaios-ci-demo-state")
_CI_DEMO_TENANCY_DIR = _CI_DEMO_STATE_ROOT / "tenancy"
_CI_DEMO_DATA_DIR = _CI_DEMO_STATE_ROOT / "data"


def cleanup_ci_runtime_state() -> list[str]:
    """Remove mutable runtime DB state created by CI smoke/tests.

    Full CI intentionally runs demo/unit/integration flows that may exercise
    sqlite-backed dev adapters. The gate must prove those flows but must not
    leave repository-local DB artifacts after completion.
    """
    root = repo_root()
    removed: list[str] = []
    for rel_root in _RUNTIME_STATE_ROOTS:
        state_root = root / rel_root
        if not state_root.exists():
            continue
        if state_root.is_file():
            removed.append(state_root.relative_to(root).as_posix())
            state_root.unlink(missing_ok=True)
            continue
        for pattern in _RUNTIME_STATE_PATTERNS:
            for path in state_root.rglob(pattern):
                if path.is_file():
                    removed.append(path.relative_to(root).as_posix())
                    path.unlink(missing_ok=True)
        _remove_empty_dirs(state_root, stop_at=root)
    if _CI_DEMO_STATE_ROOT.exists():
        shutil.rmtree(_CI_DEMO_STATE_ROOT, ignore_errors=True)
        removed.append(str(_CI_DEMO_STATE_ROOT))
    return sorted(set(removed))


def _cleanup_demo_runtime_state() -> list[str]:
    """Backward-compatible alias for the demo smoke cleanup contract."""
    return cleanup_ci_runtime_state()


def _remove_empty_dirs(path: Path, *, stop_at: Path) -> None:
    if not path.exists() or path == stop_at:
        return
    for child in sorted((p for p in path.rglob("*") if p.is_dir()), reverse=True):
        with suppress(OSError):
            child.rmdir()
    with suppress(OSError):
        path.rmdir()


def _ci_demo_env() -> dict[str, str]:
    """Return an explicit sqlite-only demo environment.

    Server deployments may keep POSTGRES_DSN/DATABASE_URL in .env. python-dotenv
    does not override existing environment keys, so setting empty values here
    prevents local CI demo smoke from accidentally entering the production-like
    Postgres path while preserving the runtime/wiring fail-closed guard.
    """
    return {
        "RUN_MODE": "demo",
        "DEMO_E2E_SMOKE": "1",
        "APP_ENV": "ci",
        "ENV": "ci",
        "TENANT_ID": "ci-demo-tenant",
        "SYSTEM_TZ": "Europe/Amsterdam",
        "CI_STEP_TIMEOUT_SECONDS": "180",
        "DATA_DIR": str(_CI_DEMO_DATA_DIR),
        "BUSINESAIOS_TENANCY_DATA_DIR": str(_CI_DEMO_TENANCY_DIR),
        "BUSINESAIOS_TENANT_REGISTRY_PATH": str(_CI_DEMO_TENANCY_DIR / "tenant_registry.json"),
        "BUSINESAIOS_TENANT_POLICY_STORE_PATH": str(_CI_DEMO_TENANCY_DIR / "tenant_policies.json"),
        "STORAGE_BACKEND": "sqlite",
        "STORAGE_DB_ENGINE": "sqlite",
        "POSTGRES_DSN": "",
        "DATABASE_URL": "",
        "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE": "",
    }


def run() -> tuple[bool, str]:
    try:
        cleanup_ci_runtime_state()
        _CI_DEMO_TENANCY_DIR.mkdir(parents=True, exist_ok=True)
        _CI_DEMO_DATA_DIR.mkdir(parents=True, exist_ok=True)
        outcome = run_command(
            ["python", "main.py"],
            env=_ci_demo_env(),
            timeout=180,
        )
    finally:
        removed = cleanup_ci_runtime_state()
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, "demo e2e smoke timed out"
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "demo e2e smoke failed"
    suffix = f"; cleaned {len(removed)} runtime state artifact(s)" if removed else ""
    return True, "demo e2e smoke passed" + suffix


__all__ = ["cleanup_ci_runtime_state", "run"]
