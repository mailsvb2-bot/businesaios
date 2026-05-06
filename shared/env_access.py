from __future__ import annotations

"""Canonical single source of truth for environment access helpers.

This module is intentionally outside ``runtime`` so config/core imports do not
need to initialize the runtime package just to parse environment variables.
That avoids runtime↔config import cycles while still keeping one parsing layer.
"""

import os
from pathlib import Path


def env_int(name: str, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
    raw = os.environ.get(name)
    try:
        value = int(raw) if raw is not None else int(default)
    except Exception:
        value = int(default)
    if lo is not None:
        value = max(int(lo), value)
    if hi is not None:
        value = min(int(hi), value)
    return value


def env_float(name: str, default: float, *, lo: float | None = None, hi: float | None = None) -> float:
    raw = os.environ.get(name)
    try:
        value = float(raw) if raw is not None else float(default)
    except Exception:
        value = float(default)
    if lo is not None:
        value = max(float(lo), value)
    if hi is not None:
        value = min(float(hi), value)
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def env_str(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else str(value)


def env_csv(name: str, default: str = "") -> list[str]:
    raw = env_str(name, default).strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def env_path(name: str, default: str = "") -> Path:
    raw = env_str(name, default).strip()
    return Path(raw).expanduser() if raw else Path(default).expanduser()


__all__ = [
    "env_bool",
    "env_csv",
    "env_float",
    "env_int",
    "env_path",
    "env_str",
]
