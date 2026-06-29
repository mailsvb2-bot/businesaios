"""Canonical serving support surface with compat alias submodules."""

from __future__ import annotations


from dataclasses import dataclass
from typing import Protocol

from runtime.platform.support.contracts.observation import Observation


class ServingRuntime(Protocol):
    def predict(self, observation: Observation):
        ...

@dataclass(frozen=True)
class ServingBudget:
    max_qps: int

@dataclass(frozen=True)
class ServingConfig:
    timeout_ms: int = 1000

@dataclass(frozen=True)
class ServingLimits:
    max_concurrency: int

@dataclass(frozen=True)
class ServingMetadata:
    name: str
    version: str

@dataclass(frozen=True)
class ServingPolicy:
    deterministic: bool = True

class ServingRegistry:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def register(self, name: str, runtime: object) -> None:
        self._items[name] = runtime

    def get(self, name: str) -> object:
        return self._items[name]

class ServingRouter:
    def route(self, runtimes: list[object]) -> object:
        if not runtimes:
            raise ValueError("No runtimes available")
        return runtimes[0]

class ServingSelector:
    def choose_name(self, names: list[str]) -> str:
        if not names:
            raise ValueError("No names available")
        return names[0]

    select = choose_name

__all__ = [
    "ServingBudget",
    "ServingConfig",
    "ServingLimits",
    "ServingMetadata",
    "ServingPolicy",
    "ServingRegistry",
    "ServingRouter",
    "ServingRuntime",
    "ServingSelector",
]
