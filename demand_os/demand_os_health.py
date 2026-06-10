from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DemandOsHealth:
    ready: bool
    reason: str
    components: tuple[str, ...] = ()


    @property
    def detail(self) -> str:
        return self.reason
