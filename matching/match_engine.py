from __future__ import annotations

from config.execution_contract import CANONICAL_OPTIMIZATION_TARGET
from matching.candidate_builder import MatchBundleBuilder, MatchCandidateBuilder
from matching.filters import MatchFilters
from matching.match_audit import MatchAudit
from matching.math_router import MatchMathSummary, MathAwareMatchRouter
from matching.ranking import MatchRanking
from observability.demand import emit_match_events as emit_match_event
from supply_state.live_state_snapshot import to_snapshot


class MatchEngine:
    def __init__(self, *, event_log: object | None = None, math_router: MathAwareMatchRouter | None = None) -> None:
        self._builder = MatchCandidateBuilder()
        self._bundle = MatchBundleBuilder()
        self._ranking = MatchRanking()
        self._filters = MatchFilters()
        self._audit = MatchAudit()
        self._event_log = event_log
        self._math_router = math_router or MathAwareMatchRouter()

    def summarize_math(
        self,
        *,
        candidates,
        node_features,
        adjacency,
        capacity_graph=None,
    ) -> MatchMathSummary:
        """Optional math enrichment for read/explain flows.

        This method never overrides canonical ranking or filtering. It only
        derives extra explanatory summaries from already-built candidates.
        """
        return self._math_router.summarize(
            candidates=candidates,
            node_features=node_features,
            adjacency=adjacency,
            capacity_graph=capacity_graph,
        )

    def _attach_math_summary(self, *, ranked, audit: dict) -> None:
        node_features = {
            str(getattr(candidate, 'business_id', '')): [
                float(getattr(candidate, 'score', 0.0)),
                float(getattr(candidate, 'intent_fit', 0.0)),
                float(getattr(candidate, 'capacity_fit', 0.0)),
            ]
            for candidate in ranked
            if getattr(candidate, 'business_id', '')
        }
        if not node_features:
            audit['math_summary'] = {
                'graph_scores': {},
                'auction_price_by_business': {},
                'max_routable_flow': 0.0,
                'transport_total_cost': 0.0,
            }
            return
        ids = list(node_features.keys())
        adjacency = {business_id: [other for other in ids if other != business_id][:2] for business_id in ids}
        graph: dict[str, dict[str, float]] = {'source': {}, 'sink': {}}
        for business_id in ids:
            graph['source'][business_id] = 1.0
            graph[business_id] = {'sink': 1.0}
        summary = self._math_router.summarize(
            candidates=ranked,
            node_features=node_features,
            adjacency=adjacency,
            capacity_graph=graph,
        )
        audit['math_summary'] = {
            'graph_scores': summary.graph_scores,
            'auction_price_by_business': summary.auction_price_by_business,
            'max_routable_flow': summary.max_routable_flow,
            'transport_total_cost': summary.transport_total_cost,
        }

    def build_bundle(self, *, request, intent, profiles, live_states, gravity_snapshot=None):
        states_by_business = {}
        duplicate_live_states: set[str] = set()
        for state in live_states:
            if state.business_id in states_by_business:
                duplicate_live_states.add(str(state.business_id))
                continue
            states_by_business[state.business_id] = state
        candidates = []
        blocked_count = 0
        duplicate_profiles: set[str] = set()
        seen_profiles: set[str] = set()
        for profile in profiles:
            if profile.business_id in seen_profiles:
                duplicate_profiles.add(str(profile.business_id))
                continue
            seen_profiles.add(profile.business_id)
            live_state = states_by_business.get(profile.business_id)
            if live_state is None:
                emit_match_event(self._event_log, 'candidate_skipped_missing_live_state', {
                    'request_id': request.request_id,
                    'business_id': profile.business_id,
                })
                continue
            breakdown = self._ranking.score_breakdown(
                intent=intent,
                profile=profile,
                live_state=live_state,
                gravity_snapshot=gravity_snapshot,
            )
            blocked = self._filters.is_blocked(
                profile=profile,
                live_state=live_state,
                finite=self._ranking.finite,
            )
            if blocked:
                blocked_count += 1
            candidate = self._builder.build(
                profile.business_id,
                breakdown,
                blocked=blocked,
            )
            if self._filters.allow(candidate) or blocked:
                candidates.append(candidate)
        ranked = self._ranking.rank(tuple(candidates))
        audit = self._audit.record(request_id=request.request_id, candidates=ranked)
        if duplicate_profiles:
            audit['duplicate_profiles'] = tuple(sorted(duplicate_profiles))
        if duplicate_live_states:
            audit['duplicate_live_states'] = tuple(sorted(duplicate_live_states))
        self._attach_math_summary(ranked=ranked, audit=audit)
        emit_match_event(self._event_log, 'bundle_built', {
            'request_id': request.request_id,
            'candidate_count': len(ranked),
            'blocked_candidate_count': blocked_count,
            'optimization_target': CANONICAL_OPTIMIZATION_TARGET,
        })
        audit['live_state_snapshots'] = {
            state.business_id: to_snapshot(state)
            for state in states_by_business.values()
        }
        return self._bundle.build(request.request_id, ranked, audit)
