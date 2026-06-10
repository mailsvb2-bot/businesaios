from __future__ import annotations

from config.execution_contract import CANONICAL_OPTIMIZATION_TARGET, DEFAULT_DELIVERY_CHANNEL
from config.routing_limits import MAX_ROUTING_CANDIDATES
from guardrails.demand_policies import DemandDecisionGuard
from matching.routing_surface import RoutingCandidateBuilder, RoutingCandidateRanker
from observability.demand import emit_routing_events as emit_routing_event
from routing.router_audit import RouterAudit
from routing.router_decision_trace import RouterDecisionTrace
from routing.router_fallback import RouterFallback
from routing.router_policy_evaluator import RouterPolicyEvaluator
from routing.router_publisher import RouterPublisher
from supply_directory.profile_lookup import get_profile
from supply_state.live_state_snapshot import from_snapshot


class DemandRouter:
    def __init__(self, *, business_directory, business_live_state_builder, event_log: object | None = None) -> None:
        self._evaluator = RouterPolicyEvaluator()
        self._trace = RouterDecisionTrace()
        self._publisher = RouterPublisher()
        self._audit = RouterAudit()
        self._fallback = RouterFallback()
        self._guard = DemandDecisionGuard()
        self._candidate_builder = RoutingCandidateBuilder()
        self._candidate_ranker = RoutingCandidateRanker()
        if not callable(getattr(business_live_state_builder, 'build', None)):
            raise ValueError('business_live_state_builder must provide build()')
        self._directory = business_directory
        self._event_log = event_log

    def _select_delivery_channel(self, *, profile) -> str:
        channels = tuple(getattr(profile, 'notification_channels', ()) or ())
        return str(channels[0]) if channels else DEFAULT_DELIVERY_CHANNEL

    def _live_state_from_match_bundle(self, *, match_bundle, business_id: str):
        snapshots = dict(getattr(match_bundle, 'audit', {}) or {}).get('live_state_snapshots') or {}
        return from_snapshot(snapshots.get(str(business_id)), business_id)



    def _build_router_input(self, *, request, intent, match_bundle) -> dict[str, object]:
        return {"request": request, "intent": intent, "match_bundle": match_bundle}


    def prepare(self, *, request, intent, match_bundle) -> dict[str, object]:
        router_input = self._build_router_input(request=request, intent=intent, match_bundle=match_bundle)
        routed = []
        blocked_reasons: dict[str, tuple[str, ...]] = {}
        skipped_reasons: dict[str, str] = {}
        preferred_channels: dict[str, str] = {}
        seen_business_ids: set[str] = set()
        for candidate in match_bundle.candidates:
            business_id = str(candidate.business_id)
            if business_id in seen_business_ids:
                skipped_reasons[business_id] = 'duplicate_match_candidate'
                continue
            seen_business_ids.add(business_id)
            profile = get_profile(self._directory, business_id)
            if profile is None:
                skipped_reasons[business_id] = 'missing_profile'
                emit_routing_event(self._event_log, 'routing_candidate_skipped_missing_profile', {
                    'request_id': request.request_id,
                    'business_id': business_id,
                })
                continue
            live_state = self._live_state_from_match_bundle(match_bundle=match_bundle, business_id=business_id)
            if live_state is None:
                skipped_reasons[business_id] = 'missing_match_live_state_snapshot'
                emit_routing_event(self._event_log, 'routing_candidate_skipped_missing_snapshot', {
                    'request_id': request.request_id,
                    'business_id': business_id,
                })
                continue
            guard_allowed, reasons = self._guard.allow(live_state=live_state)
            delta, tags = self._evaluator.evaluate(intent=intent, profile=profile, live_state=live_state)
            adjusted_score = float(candidate.score) + delta
            blocked = bool(candidate.blocked or (not guard_allowed))
            if reasons:
                blocked_reasons[business_id] = reasons
            preferred_channels[business_id] = self._select_delivery_channel(profile=profile)
            routed.append(
                self._candidate_builder.build(
                    candidate=candidate,
                    policy_tags=tags + reasons,
                    adjusted_score=adjusted_score,
                    blocked=blocked,
                )
            )
        ranked = self._candidate_ranker.rank(tuple(routed))[:MAX_ROUTING_CANDIDATES]
        trace = self._trace.build(ranked_candidates=ranked)
        trace['router_input'] = dict(router_input)
        trace['preferred_channels'] = dict(preferred_channels)
        trace['optimization_target'] = CANONICAL_OPTIMIZATION_TARGET
        if ranked:
            trace['delivery_channel'] = preferred_channels.get(ranked[0].business_id, DEFAULT_DELIVERY_CHANNEL)
        if blocked_reasons:
            trace['blocked_reasons'] = dict(blocked_reasons)
        if skipped_reasons:
            trace['skipped_reasons'] = dict(skipped_reasons)
        audit = self._audit.record(request_id=request.request_id, ranked_candidates=ranked)
        if skipped_reasons:
            audit['skipped_reasons'] = dict(skipped_reasons)
        emit_routing_event(self._event_log, 'routing_prepared', {'request_id': request.request_id, 'candidate_count': len(ranked)})
        if not ranked or all(c.blocked for c in ranked):
            return self._fallback.fallback(request_id=request.request_id, trace=trace) | {'audit': audit}
        return self._publisher.publish({'request_id': request.request_id, 'ranked_candidates': ranked, 'trace': trace, 'audit': audit})
