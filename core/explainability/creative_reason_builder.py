from __future__ import annotations

from core.creative_intelligence.models import CreativeIntelligenceSnapshot
from core.explainability.operator_reason import OperatorReason


def build_creative_reasons(snapshot: CreativeIntelligenceSnapshot) -> tuple[OperatorReason, ...]:
    return (
        OperatorReason(
            code="creative_expected_value",
            line=f"creative {snapshot.creative_id} expected_value={snapshot.expected_value_score:.3f}",
        ),
        OperatorReason(
            code="creative_downside",
            line=f"creative {snapshot.creative_id} downside={snapshot.downside_envelope:.3f}",
        ),
        OperatorReason(
            code="creative_rollout_readiness",
            line=(
                f"creative {snapshot.creative_id} "
                f"rollout_readiness={snapshot.experiment_confidence.rollout_readiness:.3f}"
            ),
        ),
    )
