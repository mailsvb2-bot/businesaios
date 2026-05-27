from __future__ import annotations

from typing import Any, Dict

from application.decisioning.candidate_observations import CandidateObservationSet
from core.reward.contracts import RewardObservationContext
from kernel.decisioning.candidate_types import CandidateObservation


class RewardObserver:
    """Observation-only layer.

    Supports two safe modes:
      1) legacy metrics observation for existing runtime flow
      2) candidate observation for decision-space-safe advisory flow
    """

    def observe(self, *args: Any, **kwargs: Any) -> Any:
        if args and isinstance(args[0], RewardObservationContext):
            return self._observe_candidates(args[0])

        if "tenant_id" in kwargs or "metrics" in kwargs or "context" in kwargs:
            return self._observe_legacy(
                tenant_id=str(kwargs.get("tenant_id") or ""),
                metrics=dict(kwargs.get("metrics") or {}),
                context=dict(kwargs.get("context") or {}),
            )

        raise TypeError("Unsupported RewardObserver.observe(...) call shape")

    def _observe_candidates(self, context: RewardObservationContext) -> CandidateObservationSet:
        observations: list[CandidateObservation] = []

        for item in context.candidates.items:
            payload = item.payload
            profit_delta = str(payload.get("profit_delta", "unknown"))
            observations.append(
                CandidateObservation(
                    candidate_id=item.candidate_id,
                    observation_name="profit_delta_observation",
                    observation_value=profit_delta,
                    details={
                        "note": (
                            "Reward layer observes outcome signals only and does not "
                            "select or narrow business action space."
                        )
                    },
                )
            )

        return CandidateObservationSet.from_iterable(observations)

    def _observe_legacy(
        self,
        *,
        tenant_id: str,
        metrics: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        revenue = float(metrics.get("revenue", 0.0) or 0.0)
        spend = float(metrics.get("spend", 0.0) or 0.0)
        profit = revenue - spend
        reward = profit

        return {
            "tenant_id": tenant_id,
            "reward": reward,
            "profit": profit,
            "revenue": revenue,
            "spend": spend,
            "context": dict(context or {}),
        }
