from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CandidateEnvelope:
    candidate_id: str
    candidate_kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class CandidateScore:
    candidate_id: str
    score_name: str
    score_value: float
    explanation: str


@dataclass(frozen=True)
class CandidateObservation:
    candidate_id: str
    observation_name: str
    observation_value: str
    details: Mapping[str, Any]
