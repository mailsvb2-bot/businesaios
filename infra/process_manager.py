from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from infra.process_spec import ProcessSpec
from observability.structured_logging import StructuredLogger


@dataclass
class ProcessManager:
    logger: StructuredLogger
    _processes: list[tuple[ProcessSpec, Callable[[], object]]] = field(default_factory=list)

    def register(self, spec: ProcessSpec, process: Callable[[], object]) -> None:
        self._processes.append((spec, process))

    def start_enabled(self) -> dict[str, object]:
        started: dict[str, object] = {}

        for spec, process in self._processes:
            if not spec.enabled:
                continue

            self.logger.info("process_starting", process_name=spec.name)
            started[spec.name] = process()
            self.logger.info("process_started", process_name=spec.name)

        return started

    def names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec, _ in self._processes)
