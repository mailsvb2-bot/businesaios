from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from contracts.action_impact_contract import (
    ActionExecutionContext,
    ActionImpact,
    ActionImpactPolicyRef,
)
from core.safety.operational.action_classifier import ActionClassifier
from core.safety.operational.action_cost_model import ActionCostModel


CANON_OPERATIONAL_ACTION_IMPACT_BUILDER = True


@dataclass(frozen=True)
class ActionImpactBuilder:
    classifier: ActionClassifier
    cost_model: ActionCostModel

    def build(self, ctx: ActionExecutionContext) -> ActionImpact:
        classified = self.classifier.classify(ctx)
        cost = self.cost_model.compute(classified.spec.cost_policy, ctx.payload)

        publication_count = self._resolve_count(
            payload=ctx.payload,
            fixed_count=classified.spec.publication_count,
            payload_key=classified.spec.payload_publication_count_key,
            enabled=classified.spec.is_publication,
        )
        outbound_count = self._resolve_count(
            payload=ctx.payload,
            fixed_count=classified.spec.outbound_count,
            payload_key=classified.spec.payload_outbound_count_key,
            enabled=classified.spec.is_outbound,
        )

        impact = ActionImpact(
            action_name=classified.action_name,
            category=classified.category,
            cost_minor=int(cost.cost_minor),
            publication_count=publication_count,
            outbound_count=outbound_count,
            strategic_change_count=1 if classified.spec.is_strategic else 0,
            rollback_event_count=int(
                classified.spec.rollback_event_count if classified.spec.is_rollback_event else 0
            ),
            requires_human_approval=bool(classified.spec.requires_human_approval),
            cost_source=cost.source,
            confidence=1.0 if classified.is_known else 0.0,
            policy_ref=ActionImpactPolicyRef(
                policy_key=f"impact:{classified.action_name}",
                version="v1",
            ),
            dimensions=dict(classified.spec.dimensions),
        )
        impact.validate()
        return impact

    @staticmethod
    def _resolve_count(
        *,
        payload: Mapping[str, object],
        fixed_count: int,
        payload_key: str | None,
        enabled: bool,
    ) -> int:
        if not enabled:
            return 0
        if payload_key:
            raw = payload.get(payload_key)
            if raw is not None:
                if isinstance(raw, bool):
                    return max(0, int(raw))
                if isinstance(raw, int):
                    return max(0, raw)
                if isinstance(raw, float):
                    return max(0, int(raw))
                if isinstance(raw, str) and raw.strip():
                    return max(0, int(float(raw.strip())))
        return max(0, int(fixed_count))


__all__ = [
    "ActionImpactBuilder",
]