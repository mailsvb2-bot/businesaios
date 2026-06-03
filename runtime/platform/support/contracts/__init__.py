from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping, Sequence

from runtime.platform.support.optimization.promotion_decision import PromotionDecision


@dataclass(frozen=True)
class Action:
    name: str
    payload: Any | None = None

@dataclass(frozen=True)
class Candidate:
    candidate_id: str

@dataclass(frozen=True)
class CheckpointRef:
    uri: str

@dataclass(frozen=True)
class EvaluationResult:
    candidate_id: str
    metrics: Mapping[str, float]

@dataclass(frozen=True)
class ExperimentRef:
    experiment_id: str

@dataclass(frozen=True)
class GovernanceEvent:
    event_type: str

@dataclass(frozen=True)
class Incident:
    incident_type: str
    description: str

@dataclass(frozen=True)
class ModelDescriptor:
    model_name: str
    version: str

@dataclass(frozen=True)
class Observation:
    data: Mapping[str, Any]

@dataclass(frozen=True)
class PolicyDescriptor:
    name: str
    version: str

@dataclass(frozen=True)
class Reward:
    value: float

@dataclass(frozen=True)
class RollbackDecision:
    candidate_id: str
    reason: str

@dataclass(frozen=True)
class TelemetryEvent:
    name: str
    payload: Mapping[str, object]

@dataclass(frozen=True)
class Transition:
    observation: Observation
    action: Action
    reward: Reward
    done: bool

@dataclass(frozen=True)
class Trajectory:
    transitions: Sequence[Transition]

@dataclass(frozen=True)
class Episode:
    trajectory: Trajectory

@dataclass(frozen=True)
class RolloutResult:
    rollout_id: str
    episodes: Sequence[Episode]

__all__ = [
    "Action",
    "Candidate",
    "CheckpointRef",
    "Episode",
    "EvaluationResult",
    "ExperimentRef",
    "GovernanceEvent",
    "Incident",
    "ModelDescriptor",
    "Observation",
    "PolicyDescriptor",
    "PromotionDecision",
    "Reward",
    "RollbackDecision",
    "RolloutResult",
    "TelemetryEvent",
    "Trajectory",
    "Transition",
]
