"""Runtime application paths.

Provides a BusinesAIOS-first home directory while preserving a narrow legacy
fallback for older single-product installs.
"""

from __future__ import annotations

from pathlib import Path

from runtime.platform.config.env_flags import env_str


def runtime_data_dir(*, app_dirname: str = ".businesaios", legacy_dirname: str = ".legacy_product") -> Path:
    """Return writable runtime data directory.

    Resolution order:
      1) BUSINESAIOS_HOME if set
      2) ~/.businesaios
      3) legacy fallback from the previous single-product install if it exists and new dir does not
    """

    env = env_str("BUSINESAIOS_HOME", "").strip()
    if env:
        path = Path(env).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    preferred = Path.home() / app_dirname
    legacy = Path.home() / legacy_dirname
    chosen = legacy if legacy.exists() and not preferred.exists() else preferred
    chosen.mkdir(parents=True, exist_ok=True)
    return chosen
