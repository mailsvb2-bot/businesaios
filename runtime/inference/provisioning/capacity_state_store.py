from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from execution.inference_capacity_contract import InferenceCapacityTier

CANON_RUNTIME_INFERENCE_CAPACITY_STATE_STORE = True


@dataclass
class InferenceCapacityState:
    active_tier: InferenceCapacityTier = InferenceCapacityTier.LOCAL_GPU
    last_transition_ts: float = field(default_factory=time)
    frozen: bool = False


class InferenceCapacityStateStore:
    def __init__(self) -> None:
        self._state = InferenceCapacityState()

    def get(self) -> InferenceCapacityState:
        return self._state

    def set_tier(self, tier: InferenceCapacityTier) -> None:
        self._state.active_tier = tier
        self._state.last_transition_ts = time()

    def set_frozen(self, frozen: bool) -> None:
        self._state.frozen = bool(frozen)
