from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentRegistered:
    experiment_id: str
    name: str
    owner: str
    subject_key: str
    audience_key: str
