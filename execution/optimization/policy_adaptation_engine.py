from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from collections.abc import Iterable

from execution.optimization.adaptation_metrics import build_scorecard
from execution.optimization.feedback_pipeline import AdaptationObservation
from execution.optimization.performance_profile_store import AdaptationCounters, EconomicAdaptationState, PerformanceProfile, RouteAdaptationState, ThresholdAdaptationState
from execution.optimization.routing_adaptation import RoutingAdaptationEngine
from execution.optimization.economic_adaptation import EconomicAdaptationEngine
from execution.optimization.threshold_adaptation import ThresholdAdaptationEngine


class PolicyAdaptationEngine:
    def __init__(self, *, routing_engine: RoutingAdaptationEngine | None = None, economic_engine: EconomicAdaptationEngine | None = None, threshold_engine: ThresholdAdaptationEngine | None = None, min_accepted_samples_for_policy_readiness: int = 5) -> None:
        self._routing_engine = routing_engine or RoutingAdaptationEngine()
        self._economic_engine = economic_engine or EconomicAdaptationEngine()
        self._threshold_engine = threshold_engine or ThresholdAdaptationEngine()
        self._min_accepted_samples_for_policy_readiness = max(1, int(min_accepted_samples_for_policy_readiness))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _route_map(routes: Iterable[RouteAdaptationState]) -> dict[str, RouteAdaptationState]:
        return {item.route_key: item for item in routes}

    def adapt_profile(self, *, current: PerformanceProfile, accepted_observations: Iterable[AdaptationObservation], rejected_count: int, last_noise_reason: str = '') -> PerformanceProfile:
        accepted = list(accepted_observations)
        counters = current.counters
        next_counters = AdaptationCounters(
            accepted_observations=counters.accepted_observations + len(accepted),
            rejected_observations=counters.rejected_observations + max(0, int(rejected_count)),
            executed=counters.executed + sum(1 for i in accepted if i.executed),
            verified=counters.verified + sum(1 for i in accepted if i.verified),
            achieved=counters.achieved + sum(1 for i in accepted if i.achieved),
        )
        routes = self._route_map(current.route_states)
        grouped: dict[str, list[AdaptationObservation]] = {}
        for item in accepted:
            grouped.setdefault(item.route_key, []).append(item)
        for route_key, group in grouped.items():
            routes[route_key] = self._routing_engine.adapt_route(current=routes.get(route_key), observations=group)
        next_route_states = tuple(sorted(routes.values(), key=lambda item: item.route_key))
        next_economic = self._economic_engine.adapt(current=current.economic if isinstance(current.economic, EconomicAdaptationState) else EconomicAdaptationState(), observations=accepted)
        next_thresholds = self._threshold_engine.adapt(current=current.thresholds if isinstance(current.thresholds, ThresholdAdaptationState) else ThresholdAdaptationState(), observations=accepted)
        next_history = current.score_history
        if accepted:
            sample_count = len(accepted)
            success_rate = sum(1 for item in accepted if item.executed) / sample_count
            verification_rate = sum(1 for item in accepted if item.verified) / sample_count
            achieved_rate = sum(1 for item in accepted if item.achieved) / sample_count
            roi_avg = sum(min(1.0, item.roi_ratio / 2.0) for item in accepted) / sample_count
            latency_score = sum(max(0.0, 1.0 - min(1.0, item.latency_ms / 60_000.0)) for item in accepted) / sample_count
            stability_score = 1.0 - min(1.0, rejected_count / max(1, sample_count + rejected_count))
            scorecard = build_scorecard(sample_count=sample_count, success_rate=success_rate, verification_rate=verification_rate, roi_score=max(roi_avg, achieved_rate), latency_score=latency_score, stability_score=stability_score)
            next_history = tuple((list(current.score_history) + [scorecard.composite_score])[-100:])
        return replace(current, counters=next_counters, route_states=next_route_states, economic=next_economic, thresholds=next_thresholds, score_history=next_history, last_noise_reason=str(last_noise_reason), last_updated_at=self._now_iso())

    def runtime_policy_view(self, *, profile: PerformanceProfile) -> dict[str, object]:
        adaptation_ready = profile.counters.accepted_observations >= self._min_accepted_samples_for_policy_readiness
        routing_table = self._routing_engine.recommend_routing_table(routes=profile.route_states)
        route_diagnostics = [
            {
                'route_key': route.route_key,
                'weight': route.weight,
                'success_rate': route.success_rate,
                'verification_rate': route.verification_rate,
                'roi_score': route.roi_score,
                'sample_count': route.sample_count,
            }
            for route in sorted(profile.route_states, key=lambda item: item.weight, reverse=True)
        ]
        preferred_route_key = route_diagnostics[0]['route_key'] if route_diagnostics else None
        readiness_reason = 'ready' if adaptation_ready else 'insufficient_accepted_samples'
        return {
            'tenant_id': profile.tenant_id,
            'business_id': profile.business_id,
            'capability_key': profile.capability_key,
            'routing_table': routing_table,
            'preferred_route_key': preferred_route_key,
            'route_diagnostics': route_diagnostics,
            'economic': asdict(profile.economic),
            'thresholds': asdict(profile.thresholds),
            'counters': asdict(profile.counters),
            'score_history': list(profile.score_history),
            'last_noise_reason': profile.last_noise_reason,
            'last_updated_at': profile.last_updated_at,
            'adaptation_ready': adaptation_ready,
            'policy_readiness_reason': readiness_reason,
            'evidence_only': True,
            'must_not_issue_decision': True,
        }

__all__ = ['PolicyAdaptationEngine']
