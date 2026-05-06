from __future__ import annotations

from importlib import import_module


def _env_str(name: str, default: str = "") -> str:
    env_flags = import_module("runtime.platform.config.env_flags")
    return str(env_flags.env_str(name, default))


def is_strict_mode() -> bool:
    env = _env_str("ENV", "dev").lower()
    if env in {"prod", "production"}:
        return True
    return _env_str("ECONOMIC_STRICT", "0") == "1"
