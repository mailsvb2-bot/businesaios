from __future__ import annotations

from dataclasses import dataclass, field

from application.world_state.history_sample import HistorySample


@dataclass
class HistoryWindow:
    capacity: int
    samples: list[HistorySample] = field(default_factory=list)

    def append(self, sample: HistorySample) -> None:
        self.samples.append(sample)
        if len(self.samples) > self.capacity:
            self.samples[:] = self.samples[-self.capacity :]

    def all(self) -> tuple[HistorySample, ...]:
        return tuple(self.samples)
