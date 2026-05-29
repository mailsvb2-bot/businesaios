from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


class VariantReadModel(Protocol):
    def get_variant(self, *, user_id: str, step: str, seed: int) -> str | None: ...


@dataclass(frozen=True)
class VariantChoice:
    step: str
    variant_id: str
    rollout_group: str | None = None
    canary: bool = False


class VariantSelector:
    """Pure selector over a read-model.

    Selection stays read-only; writes still belong to DecisionCore effects.
    """

    def __init__(self, read_model: VariantReadModel, *, seed: int = 0):
        self._rm = read_model
        self._seed = int(seed)

    def choose_variant(self, *, user_id: str, step: str) -> VariantChoice | None:
        vid = self._rm.get_variant(user_id=user_id, step=step, seed=self._seed)
        if not vid:
            return None
        return VariantChoice(step=step, variant_id=str(vid), rollout_group=None, canary=False)

    select = choose_variant
