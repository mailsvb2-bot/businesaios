from __future__ import annotations

"""Canonical environment access helpers for core/config surfaces.

CANON_COMPAT_SHIM = True

Implementation is delegated to :mod:`shared.env_access` so core/config/runtime
share one parsing layer without importing the ``runtime`` package during config
bootstrap.
"""

from pathlib import Path

from shared import env_access as _shared


def env_int(name: str, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
    return _shared.env_int(name, default, lo=lo, hi=hi)


def env_float(name: str, default: float, *, lo: float | None = None, hi: float | None = None) -> float:
    return _shared.env_float(name, default, lo=lo, hi=hi)


def env_bool(name: str, default: bool = False) -> bool:
    return _shared.env_bool(name, default)


def env_str(name: str, default: str = "") -> str:
    return _shared.env_str(name, default)


def env_csv(name: str, default: str = "") -> list[str]:
    return _shared.env_csv(name, default)


def env_path(name: str, default: str = "") -> Path:
    return _shared.env_path(name, default)


def env_bool_flag(name: str, default: bool = False) -> bool:
    return env_bool(name, default)


def env_int_flag(name: str, default: int) -> int:
    return env_int(name, default)


def env_str_flag(name: str, default: str = "") -> str:
    return env_str(name, default)


__all__ = [
    "env_bool",
    "env_bool_flag",
    "env_csv",
    "env_float",
    "env_int",
    "env_int_flag",
    "env_path",
    "env_str",
    "env_str_flag",
]
