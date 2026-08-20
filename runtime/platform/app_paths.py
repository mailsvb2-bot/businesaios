"""Runtime application paths with one shared production runtime-root contract."""

from __future__ import annotations

from pathlib import Path

from runtime.platform.config.env_flags import env_str
from shared.runtime_paths import shared_runtime_root


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
