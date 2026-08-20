"""Runtime application paths with one shared production runtime-root contract."""

from __future__ import annotations

from pathlib import Path

from runtime.platform.config.env_flags import env_str

_SHARED_RUNTIME_ENV_NAMES = (
    "BUSINESAIOS_DATA_DIR",
    "APP_RUNTIME_DATA_DIR",
    "BAIOS_DATA_DIR",
    "DATA_DIR",
)


def shared_runtime_root() -> Path | None:
    """Resolve the canonical shared runtime root when production configured one."""
    for name in _SHARED_RUNTIME_ENV_NAMES:
        value = env_str(name, "").strip()
        if value:
            return Path(value).expanduser().resolve()
    return None


def runtime_data_dir(*, app_dirname: str = ".businesaios", legacy_dirname: str = ".legacy_product") -> Path:
    """Return writable runtime data directory without writing into the deploy tree."""
    explicit_home = env_str("BUSINESAIOS_HOME", "").strip()
    if explicit_home:
        chosen = Path(explicit_home).expanduser().resolve()
    elif (shared := shared_runtime_root()) is not None:
        chosen = shared
    else:
        preferred = Path.home() / app_dirname
        legacy = Path.home() / legacy_dirname
        chosen = legacy if legacy.exists() and not preferred.exists() else preferred
    chosen.mkdir(parents=True, exist_ok=True)
    return chosen
