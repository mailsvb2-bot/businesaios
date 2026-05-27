from __future__ import annotations

"""Canonical environment access helpers for platform/runtime/core code."""

from pathlib import Path

# historical canonical import surface: from runtime.boot.env import env_bool, env_float, env_int, env_str
from shared.env_access import env_bool, env_float, env_int, env_str
from shared.env_access import env_csv as _env_csv


def env_csv(name: str, default: str = "") -> tuple[str, ...]:
    """Return a normalized tuple parsed from a comma-separated env var."""
    return tuple(_env_csv(name, default))


def env_path(name: str, default: str | Path) -> Path:
    """Return a filesystem path using the canonical env access surface."""
    return Path(env_str(name, str(default)))


__all__ = [
    "env_bool",
    "env_csv",
    "env_float",
    "env_int",
    "env_path",
    "env_str",
]
