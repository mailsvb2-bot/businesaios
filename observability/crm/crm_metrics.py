from __future__ import annotations


class CrmMetrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def inc(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + int(amount)
