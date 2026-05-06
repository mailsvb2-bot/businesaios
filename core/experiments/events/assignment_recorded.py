from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssignmentRecorded:
    assignment_id: str
    experiment_id: str
    subject_id: str
    variant_id: str
    correlation_id: str
