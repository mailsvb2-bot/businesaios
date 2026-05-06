from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from infra.background_job_models import BackgroundJobSpec
from observability.structured_logging import StructuredLogger


@dataclass
class BackgroundJobs:
    logger: StructuredLogger
    _jobs: list[tuple[BackgroundJobSpec, Callable[[], None]]] = field(default_factory=list)

    def register(self, spec: BackgroundJobSpec, job: Callable[[], None]) -> None:
        self._jobs.append((spec, job))

    def run_enabled_once(self) -> int:
        executed = 0
        for spec, job in self._jobs:
            if not spec.enabled:
                continue
            self.logger.info("background_job_started", job_name=spec.name)
            job()
            self.logger.info("background_job_completed", job_name=spec.name)
            executed += 1
        return executed

    def names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec, _ in self._jobs)
