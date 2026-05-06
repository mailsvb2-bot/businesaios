from __future__ import annotations

from copy import deepcopy
from typing import Any


class SchedulerAdapter:
    """Records scheduled jobs for local execution planning."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self) -> None:
        self._jobs: list[dict[str, Any]] = []

    def schedule(self, job_name: str, payload: Any) -> None:
        self._jobs.append({"job_name": str(job_name), "payload": deepcopy(payload)})

    def jobs(self) -> list[dict[str, Any]]:
        return [{"job_name": item["job_name"], "payload": deepcopy(item["payload"])} for item in self._jobs]


class SecretsManagerAdapter:
    """Local secret bag for non-production support flows."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._values: dict[str, Any] = dict(initial or {})

    def set(self, key: str, value: Any) -> None:
        self._values[str(key)] = deepcopy(value)

    def get(self, key: str, default: Any | None = None) -> Any:
        value = self._values.get(str(key), default)
        return deepcopy(value)

    def require(self, key: str) -> Any:
        lookup_key = str(key)
        if lookup_key not in self._values:
            raise KeyError(lookup_key)
        return deepcopy(self._values[lookup_key])

__all__ = [
    "SchedulerAdapter",
    "SecretsManagerAdapter",
]
