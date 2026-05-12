from __future__ import annotations

import shutil
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


def _cleanup_demo_runtime_state() -> list[str]:
    """Remove mutable runtime state created by the demo E2E smoke.

    The smoke proves boot -> DecisionCore -> RuntimeExecutor. It must not leave
    repository-local sqlite/state artifacts or mutate tracked tenancy JSON.
    Runtime tenancy state is routed to /tmp via explicit env vars below; this
    cleanup also removes repository-local tenancy DB fallbacks if any legacy path
    still creates them during smoke execution.
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
    return sorted(removed)


def _remove_empty_dirs(path: Path, *, stop_at: Path) -> None:
    if not path.exists() or path == stop_at:
        return
    for child in sorted((p for p in path.rglob("*") if p.is_dir()), reverse=True):
        try:
            child.rmdir()
        except OSError:
            pass
    try:
        path.rmdir()
    except OSError:
        pass


def run() -> tuple[bool, str]:
    try:
        _cleanup_demo_runtime_state()
        _CI_DEMO_TENANCY_DIR.mkdir(parents=True, exist_ok=True)
        _CI_DEMO_DATA_DIR.mkdir(parents=True, exist_ok=True)
        outcome = run_command(
            ["python", "main.py"],
            env={
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
            },
            timeout=180,
        )
    finally:
        removed = _cleanup_demo_runtime_state()
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, "demo e2e smoke timed out"
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "demo e2e smoke failed"
    suffix = f"; cleaned {len(removed)} runtime state artifact(s)" if removed else ""
    return True, "demo e2e smoke passed" + suffix


__all__ = ["run"]
