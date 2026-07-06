from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class RecommendationSource(Protocol):
    def recommendation(self) -> Mapping[str, Any]:
        ...


class BlockingGuard(Protocol):
    def allows(self, payload: Mapping[str, Any]) -> bool:
        ...

__all__ = [
    "BlockingGuard",
    "RecommendationSource",
]
