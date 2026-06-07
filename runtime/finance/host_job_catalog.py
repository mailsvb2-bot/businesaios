from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from collections.abc import Mapping

from runtime.finance.job_spec import FinanceJobSpec


@dataclass(frozen=True)
class HostJobRegistration:
    namespace: str
    jobs: Mapping[str, Callable[[dict], object]]
    specs: Mapping[str, FinanceJobSpec]
    orchestrator: object


class HostRuntimeJobCatalog:
    def __init__(self) -> None:
        self._registrations: dict[str, HostJobRegistration] = {}

    def register_namespace(
        self,
        *,
        namespace: str,
        jobs: Mapping[str, Callable[[dict], object]],
        specs: Mapping[str, FinanceJobSpec],
        orchestrator: object,
    ) -> None:
        self._registrations[namespace] = HostJobRegistration(
            namespace=namespace,
            jobs=dict(jobs),
            specs=dict(specs),
            orchestrator=orchestrator,
        )

    def namespaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    def get(self, namespace: str) -> HostJobRegistration:
        return self._registrations[namespace]

    def all_jobs(self) -> dict[str, Callable[[dict], object]]:
        merged: dict[str, Callable[[dict], object]] = {}
        for registration in self._registrations.values():
            merged.update(registration.jobs)
        return merged
