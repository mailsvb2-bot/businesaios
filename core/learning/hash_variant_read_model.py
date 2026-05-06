from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class StepSplit:
    """A/B split for a given step."""

    split_a: float = 0.5
    a_id: str = "A"
    b_id: str = "B"


class HashVariantReadModel:
    """Deterministic variant read-model.

    Canonical properties:
    - read-only (no writes)
    - deterministic per (step, tenant, user, seed)
    - configurable per step

    This is a safe default until a persisted variant assignment read-model is introduced.
    """

    def __init__(self, *, splits: Dict[str, StepSplit] | None = None, tenant_id: str = "default") -> None:
        self._splits = dict(splits or {})
        self._tenant_id = str(tenant_id or "default")

    def get_variant(self, *, user_id: str, step: str, seed: int) -> str | None:
        step = str(step or "").strip()
        if not step:
            return None
        split = self._splits.get(step, StepSplit())
        # Deterministic hash -> [0,1)
        key = f"{seed}|{step}|{self._tenant_id}|{user_id}".encode("utf-8")
        h = hashlib.sha256(key).digest()
        x = int.from_bytes(h[:8], "big") / float(2**64)
        return split.a_id if x < float(split.split_a) else split.b_id
