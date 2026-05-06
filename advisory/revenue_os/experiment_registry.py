from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from advisory.revenue_os.contracts import RevenueExperiment, _required_text

CANON_ADVISORY_REVENUE_OS_EXPERIMENT_REGISTRY = True


@dataclass(frozen=True, slots=True)
class RegisteredExperiment:
    dedup_key: str
    experiment: RevenueExperiment


class ExperimentRegistry(Protocol):
    def get(self, dedup_key: str) -> RegisteredExperiment | None: ...
    def put_if_absent(self, *, dedup_key: str, experiment: RevenueExperiment) -> RegisteredExperiment: ...


class InMemoryExperimentRegistry:
    def __init__(self) -> None:
        self._items: dict[str, RegisteredExperiment] = {}

    def get(self, dedup_key: str) -> RegisteredExperiment | None:
        return self._items.get(_required_text(dedup_key, field_name='dedup_key'))

    def put_if_absent(self, *, dedup_key: str, experiment: RevenueExperiment) -> RegisteredExperiment:
        normalized_key = _required_text(dedup_key, field_name='dedup_key')
        existing = self._items.get(normalized_key)
        if existing is not None:
            return existing
        registered = RegisteredExperiment(dedup_key=normalized_key, experiment=experiment.normalized_copy())
        self._items[normalized_key] = registered
        return registered


__all__ = ['CANON_ADVISORY_REVENUE_OS_EXPERIMENT_REGISTRY', 'ExperimentRegistry', 'InMemoryExperimentRegistry', 'RegisteredExperiment']
