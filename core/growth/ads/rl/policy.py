from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from collections.abc import Sequence

from .contracts import AdsRLAction, AdsRLState


@dataclass(frozen=True)
class PolicyDecision:
    policy_id: str
    action: AdsRLAction
    confidence: float
    reason: str


class AdsRLPolicy(Protocol):
    """Pure policy interface.

    Policies must be deterministic given the same inputs when possible.
    Randomness should be derived from explicit seeds.
    """

    def select_action(self, *, state: AdsRLState, actions: Sequence[AdsRLAction]) -> PolicyDecision: ...
