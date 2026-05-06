from __future__ import annotations

from typing import Callable

from runtime.boot.finance_boot import register_finance_jobs


class FinanceJobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Callable[[dict], object]] = {}
        register_finance_jobs(self._jobs)

    def get(self, name: str) -> Callable[[dict], object]:
        return self._jobs[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._jobs))

    def all(self) -> dict[str, Callable[[dict], object]]:
        return dict(self._jobs)
