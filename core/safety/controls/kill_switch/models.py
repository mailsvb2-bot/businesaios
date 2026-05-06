from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KillSwitchSnapshot:
    action_prefix: str
    active: bool
    reason: str = ""
