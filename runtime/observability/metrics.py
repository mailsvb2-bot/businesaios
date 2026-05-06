from __future__ import annotations

"""Canonical runtime-owned in-memory metrics store."""


CANON_RUNTIME_METRICS_OWNER = True


class Metrics:
    def __init__(self) -> None:
        self._values: dict[str, float] = {}

    def set(self, name: str, value: float) -> None:
        self._values[str(name)] = float(value)

    def get(self, name: str) -> float:
        return self._values[str(name)]

    def snapshot(self) -> dict[str, float]:
        return dict(self._values)


__all__ = ["CANON_RUNTIME_METRICS_OWNER", "Metrics"]
