"""Canonical shared runtime-root resolution across architecture layers."""

from __future__ import annotations

from pathlib import Path

from shared.env_access import env_str

_SHARED_RUNTIME_ENV_NAMES = ("BUSINESAIOS_DATA_DIR", "APP_RUNTIME_DATA_DIR", "BAIOS_DATA_DIR", "DATA_DIR")


def shared_runtime_root() -> Path | None:
    for name in _SHARED_RUNTIME_ENV_NAMES:
        value = env_str(name, "").strip()
        if value:
            return Path(value).expanduser().resolve()
    return None
