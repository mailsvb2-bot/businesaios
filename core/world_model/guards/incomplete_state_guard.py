from __future__ import annotations

from config.world_model_completeness_policy import (
    DEFAULT_WORLD_MODEL_COMPLETENESS_POLICY,
    WorldModelCompletenessPolicy,
)
from core.world_model.errors import IncompleteStateError
from core.world_model.types import CompletenessReport


class IncompleteStateGuard:
    def __init__(
        self,
        *,
        min_score: float | None = None,
        policy: WorldModelCompletenessPolicy | None = None,
    ) -> None:
        self._policy = policy or DEFAULT_WORLD_MODEL_COMPLETENESS_POLICY
        self._min_score = float(self._policy.min_score if min_score is None else min_score)

    def validate(self, *, completeness: CompletenessReport) -> None:
        if float(completeness.score) < self._min_score:
            raise IncompleteStateError(
                f"{self._policy.error_prefix} "
                f"score={completeness.score} missing={list(completeness.missing_fields)}"
            )
