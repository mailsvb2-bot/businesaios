from __future__ import annotations

from dataclasses import dataclass


CANON_INFERENCE_COOLDOWN_POLICY = True


@dataclass(frozen=True)
class InferenceCooldownPolicy:
    escalate_cooldown_seconds: int = 300
    deescalate_cooldown_seconds: int = 900
