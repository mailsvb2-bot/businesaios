from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.assumptions.assumption_types import Assumption


class AssumptionRegistry:
    def __init__(self) -> None:
        self._assumptions: dict[str, Assumption] = {}

    def register(self, assumption: Assumption) -> None:
        self._assumptions[assumption.key] = assumption

    def get(self, key: str) -> Assumption | None:
        return self._assumptions.get(key)

    def all(self) -> tuple[Assumption, ...]:
        return tuple(self._assumptions.values())

    def defaults(self) -> dict[str, Decimal]:
        return {item.key: item.value for item in self._assumptions.values()}
