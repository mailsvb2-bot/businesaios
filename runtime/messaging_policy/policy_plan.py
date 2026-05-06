from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyPlan:
    ordered_channels: tuple[str, ...]
    reason_codes: tuple[str, ...]
    terminal_reason: str = ""

    @property
    def primary_channel(self) -> str | None:
        if not self.ordered_channels:
            return None
        return self.ordered_channels[0]
