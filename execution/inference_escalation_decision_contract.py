from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from execution.inference_capacity_contract import InferenceCapacityTier


CANON_INFERENCE_ESCALATION_DECISION_CONTRACT = True


class InferenceEscalationAction(str, Enum):
    STAY = 'stay'
    ESCALATE = 'escalate'
    DEESCALATE = 'deescalate'
    SWITCH_PROVIDER = 'switch_provider'


@dataclass(frozen=True)
class InferenceEscalationDecision:
    action: InferenceEscalationAction
    target_tier: InferenceCapacityTier
    reason: str
    cooldown_seconds: int
