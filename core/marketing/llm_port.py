from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol


@dataclass(frozen=True)
class MarketingVariant:
    key: str
    text: str
    rationale: str = ""


class MarketingLLM(Protocol):
    def generate_variants(self, *, context: str, goal: str, n: int = 5) -> list[MarketingVariant]:
        ...
