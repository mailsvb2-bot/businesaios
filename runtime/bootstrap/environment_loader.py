from __future__ import annotations
from pathlib import Path
import os
import sys
import tempfile
from config.env_flags import env_bool, env_str
from runtime.bootstrap.bootstrap_contract import BootstrapEnvironment, BootstrapMode

def _running_under_pytest() -> bool:
    return (
        "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in sys.modules
        or any("pytest" in (arg or "") for arg in sys.argv)
    )

def _resolve_mode() -> BootstrapMode:
    if _running_under_pytest():
        return BootstrapMode.TEST
    raw = (env_str("APP_ENV", env_str("ENV", "dev")) or "dev").strip().lower()
    if raw in {"prod", "production"}:
        return BootstrapMode.PROD
    if raw in {"test", "pytest"}:
        return BootstrapMode.TEST
    return BootstrapMode.DEV

def _runtime_dir_configuration(*, root: Path, mode: BootstrapMode) -> tuple[Path, str]:
    explicit = env_str("RUNTIME_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve(), "env"
    if mode is BootstrapMode.TEST:
        return (Path(tempfile.gettempdir()) / "businesaios-runtime" / root.name).resolve(), "tempfile"
    return (root / ".runtime").resolve(), "project_root"

def load_bootstrap_environment(*, project_root: str | Path | None = None) -> BootstrapEnvironment:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    mode = _resolve_mode()
    runtime_dir, runtime_dir_source = _runtime_dir_configuration(root=root, mode=mode)
    manifest_path = Path(
        env_str("RELEASE_MANIFEST_PATH", str(root / "release" / "manifest.json"))
    ).resolve()
    strict_default = mode is BootstrapMode.PROD
    lock_default = mode is not BootstrapMode.TEST
    return BootstrapEnvironment(
        mode=mode,
        project_root=root,
        runtime_dir=runtime_dir,
        release_manifest_path=manifest_path,
        strict=env_bool("BOOTSTRAP_STRICT", strict_default),
        release_attestation_required=env_bool("RELEASE_ATTEST", mode is BootstrapMode.PROD),
        singleton_lock_enabled=env_bool("BOOTSTRAP_SINGLETON_LOCK", lock_default),
        allow_legacy_entrypoints=env_bool("ALLOW_LEGACY_BOOTSTRAP_ENTRYPOINTS", False),
        extra={
            "app_env": env_str("APP_ENV", ""),
            "env": env_str("ENV", ""),
            "run_mode": env_str("RUN_MODE", ""),
            "runtime_dir_source": runtime_dir_source,
        },
    )
