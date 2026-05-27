from __future__ import annotations

from time import time

CANON_RUNTIME_INFERENCE_UPGRADE_COOLDOWN_TRACKER = True


class InferenceUpgradeCooldownTracker:
    def __init__(self) -> None:
        self._ready_at: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        return time() >= self._ready_at.get(key, 0.0)

    def arm(self, key: str, seconds: int) -> None:
        self._ready_at[key] = time() + max(0, int(seconds))
