from __future__ import annotations

from core.strategic_horizon.constants import MODE_COOLDOWN_SECONDS


class CooldownState:
    def __init__(self) -> None:
        self.last_mode = None
        self.last_switch_ts: float = 0.0

    def apply(self, proposed, ts: float):
        if self.last_mode is None:
            self.commit(proposed, ts)
            return proposed
        if proposed != self.last_mode:
            if ts - self.last_switch_ts < MODE_COOLDOWN_SECONDS:
                return self.last_mode
            self.commit(proposed, ts)
        return self.last_mode

    def commit(self, mode, ts: float) -> None:
        self.last_mode = mode
        self.last_switch_ts = ts
