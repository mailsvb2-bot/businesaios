from __future__ import annotations

from config.execution_contract import CANONICAL_DECISION_PATH, CANONICAL_OPTIMIZATION_TARGET, DEFAULT_DELIVERY_CHANNEL
from config.routing_limits import MAX_RUNNER_UPS
from contracts.matching.routing_decision import RoutingDecision
from kernel.decision_candidate import DecisionCandidate
from core.constraints.decision import DecisionConstraints
from kernel.decision_request import DecisionRequest
from kernel.decision_space import DecisionSpace
from demand_decision.decision_package_validator import DecisionPackageValidator
from shared.numbers import coerce_float
from config.risk_evaluation_policy import DEFAULT_CANONICAL_DECISION_BRIDGE_POLICY


class CanonicalDemandDecisionBridge:
    def __init__(self, *, decision_core: object) -> None:
        self._decision_core = decision_core
        self._validator = DecisionPackageValidator()

    def _candidate_from_routing(self, routing_candidate, preferred_channels: dict[str, str]) -> DecisionCandidate:
        business_id = str(getattr(routing_candidate, 'business_id', '') or '').strip()
        if not business_id:
            raise ValueError('routing candidate requires business_id')
        raw_channel = str(preferred_channels.get(business_id) or DEFAULT_DELIVERY_CHANNEL).strip()
        channel = raw_channel or DEFAULT_DELIVERY_CHANNEL
        trace = dict(getattr(routing_candidate, 'trace', {}) or {})
        policy = DEFAULT_CANONICAL_DECISION_BRIDGE_POLICY
        adjusted = max(policy.minimum_score, coerce_float(trace.get('adjusted_score', getattr(routing_candidate, 'rank_score', 0.0)), 0.0))
        match_score = max(policy.minimum_score, coerce_float(trace.get('match_score', adjusted), adjusted))
        risk_score = coerce_float(trace.get('risk_score', 0.0), 0.0, minimum=policy.minimum_score, maximum=policy.maximum_score)
        confidence = max(policy.minimum_score, min(policy.maximum_score, policy.base_confidence + (adjusted * policy.adjusted_confidence_weight)))
        return DecisionCandidate(
            action_type='route_lead',
            channel=channel,
            score=adjusted,
            expected_value=max(policy.minimum_score, adjusted),
            confidence=confidence,
            reasons=['demand_route_candidate'],
            payload={
                'business_id': business_id,
                'rank_score': adjusted,
                'match_score': match_score,
                'adjusted_score': adjusted,
                'risk_score': risk_score,
                'routing_trace': trace,
            },
        )

    def _issue_decision(self, *, decision_space: DecisionSpace, constraints: DecisionConstraints, request: DecisionRequest):
        issue = getattr(self._decision_core, 'issue', None)
        if callable(issue):
            return issue(decision_space, constraints, request=request)
        decide = getattr(self._decision_core, 'decide', None)
        if callable(decide):
            return decide(decision_space, constraints, request=request)
        raise AttributeError('decision_core must implement canonical issue() or decide()')



    def evaluate(self, *, request, routing_preparation) -> RoutingDecision:
        return self.issue(request=request, routing_preparation=routing_preparation)
    decide = evaluate

    def issue(self, *, request, routing_preparation) -> RoutingDecision:
        prepared = dict(routing_preparation)
        request_id = str(getattr(request, 'request_id', '') or '')
        if not request_id:
            raise ValueError('request requires request_id')
        prepared.setdefault('request_id', request_id)
        package = self._validator.validate(prepared)
        if str(package.get('request_id') or '') != request_id:
            raise ValueError('routing preparation request_id must match request')
        ranked = tuple(package.get('ranked_candidates') or ())
        trace = dict(package.get('trace') or {})
        preferred_channels = {
            str(key).strip(): (str(value).strip() or DEFAULT_DELIVERY_CHANNEL)
            for key, value in dict(trace.get('preferred_channels') or {}).items()
            if str(key).strip()
        }
        seen_business_ids: set[str] = set()
        candidates: list[DecisionCandidate] = []
        blocked_count = 0
        for candidate in ranked:
            if getattr(candidate, 'blocked', False):
                blocked_count += 1
                continue
            business_id = str(getattr(candidate, 'business_id', '') or '').strip()
            if not business_id or business_id in seen_business_ids:
                continue
            seen_business_ids.add(business_id)
            candidates.append(self._candidate_from_routing(candidate, preferred_channels))
        if not candidates:
            decision_trace = dict(trace)
            decision_trace['decision_path'] = CANONICAL_DECISION_PATH
            decision_trace['optimization_target'] = CANONICAL_OPTIMIZATION_TARGET
            decision_trace['request_id'] = request_id
            decision_trace['selected_from_candidates'] = 0
            decision_trace['blocked_candidate_count'] = blocked_count
            decision_trace['manual_review_reason'] = str(trace.get('manual_review_reason') or 'no_safe_candidates')
            return RoutingDecision(
                request_id=request_id,
                selected_business_id=None,
                runner_up_business_ids=(),
                trace=decision_trace,
                requires_manual_review=True,
            )
        constraints = DecisionConstraints()
        decision_space = DecisionSpace(candidates=tuple(candidates))
        decision_request = DecisionRequest(
            business_id='demand_network',
            objective=constraints.objective_name,
            input_bundle_id=request_id,
            request_id=request_id,
            metadata={'origin': 'demand_os', 'candidate_count': len(candidates), 'customer_id': str(getattr(request, 'customer_id', '') or '')},
        )
        result, _audit = self._issue_decision(
            decision_space=decision_space,
            constraints=constraints,
            request=decision_request,
        )
        selected_business_id = None
        runner_ups: tuple[str, ...] = ()
        if result.candidate is not None:
            selected_business_id = str(result.candidate.payload.get('business_id') or '').strip() or None
            runner_ups = tuple(
                str(candidate.payload.get('business_id') or '').strip()
                for candidate in candidates
                if str(candidate.payload.get('business_id') or '').strip() and str(candidate.payload.get('business_id') or '').strip() != selected_business_id
            )[:MAX_RUNNER_UPS]
        decision_trace = dict(trace)
        decision_trace['decision_path'] = CANONICAL_DECISION_PATH
        decision_trace['optimization_target'] = str(trace.get('optimization_target') or CANONICAL_OPTIMIZATION_TARGET)
        decision_trace['decision_id'] = result.trace.decision_id
        decision_trace['request_id'] = request_id
        decision_trace['selected_from_candidates'] = len(candidates)
        decision_trace['blocked_candidate_count'] = blocked_count
        if selected_business_id is None:
            decision_trace['manual_review_reason'] = str(trace.get('manual_review_reason') or 'decision_core_rejected_all_candidates')
        else:
            decision_trace['delivery_channel'] = str(result.candidate.channel or preferred_channels.get(selected_business_id) or DEFAULT_DELIVERY_CHANNEL)
        return RoutingDecision(
            request_id=request_id,
            selected_business_id=selected_business_id,
            runner_up_business_ids=runner_ups,
            trace=decision_trace,
            requires_manual_review=selected_business_id is None,
        )
