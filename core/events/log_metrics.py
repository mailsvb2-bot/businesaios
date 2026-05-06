from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EventLogMetrics:
    emitted_total: int = 0
    append_failures: int = 0
    backend_fallback_reads: int = 0

    def on_emit(self) -> None:
        self.emitted_total += 1

    def on_append_failure(self) -> None:
        self.append_failures += 1

    def on_backend_fallback_read(self) -> None:
        self.backend_fallback_reads += 1

    def snapshot(self) -> dict[str, int]:
        return {
            "emitted_total": int(self.emitted_total),
            "append_failures": int(self.append_failures),
            "backend_fallback_reads": int(self.backend_fallback_reads),
        }
