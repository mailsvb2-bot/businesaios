from __future__ import annotations

from core.experiments.errors import AssignmentValidationError


class AssignmentInputGuard:
    def validate(self, *, subject_id: str, correlation_id: str, assigned_at: str) -> None:
        if not subject_id.strip():
            raise AssignmentValidationError("subject_id must be non-empty")
        if not correlation_id.strip():
            raise AssignmentValidationError("correlation_id must be non-empty")
        if not assigned_at.strip():
            raise AssignmentValidationError("assigned_at must be non-empty")
