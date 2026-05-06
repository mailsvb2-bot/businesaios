from __future__ import annotations

from core.experiments.enums import ExperimentStatus
from core.experiments.errors import ExperimentOverlapViolation


class ExperimentOverlapGuard:
    _BLOCKING_STATUSES = {
        ExperimentStatus.DRAFT,
        ExperimentStatus.ACTIVE,
        ExperimentStatus.PAUSED,
    }

    def ensure_no_overlap(self, candidate_plan, existing_plans) -> None:
        candidate_keys = set(candidate_plan.overlap_keys)
        if not candidate_keys:
            return
        for existing in existing_plans:
            if existing.experiment_id == candidate_plan.experiment_id:
                continue
            if existing.status not in self._BLOCKING_STATUSES:
                continue
            if existing.subject_key != candidate_plan.subject_key:
                continue
            if existing.audience_key != candidate_plan.audience_key:
                continue
            existing_keys = set(existing.overlap_keys)
            if candidate_keys.intersection(existing_keys):
                raise ExperimentOverlapViolation(
                    f"experiment overlap detected with {existing.experiment_id}"
                )
