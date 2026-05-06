from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _RuntimeConstructionToken:
    marker: str = "runtime_internal_construction_token"


_RUNTIME_CONSTRUCTION_TOKEN = _RuntimeConstructionToken()


def runtime_construction_token() -> _RuntimeConstructionToken:
    return _RUNTIME_CONSTRUCTION_TOKEN


def is_valid_runtime_construction_token(value: object) -> bool:
    return value is _RUNTIME_CONSTRUCTION_TOKEN
