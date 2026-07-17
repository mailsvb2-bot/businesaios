from __future__ import annotations

from dataclasses import asdict
from typing import Any

from config.execution_contract import (
    CANONICAL_DECISION_PATH,
    CANONICAL_OPTIMIZATION_TARGET,
    DEFAULT_DELIVERY_CHANNEL,
)
from config.risk_evaluation_policy import (
    DEFAULT_CANONICAL_DECISION_BRIDGE_POLICY,
)
from config.routing_limits import MAX_RUNNER_UPS
from contracts.matching.routing_decision import RoutingDecision
from core.actions.names import ACTION_ROUTE_LEAD_V1
from core.constraints.decision import DecisionConstraints
from demand_decision.decision_package_validator import DecisionPackageValidator
from kernel.decision_candidate import DecisionCandidate
from kernel.world_state import WorldStateV1
from runtime.decision_gateway import issue_runtime_decision
from shared.numbers import coerce_float

CANON_DEMAND_BRIDGE_ADAPTS_SIGNED_ROUTE_DECISION = True


def _request_timestamp_ms(request: Any) -> int:
    value = getattr(request, "requested_at", None)
    timestamp = getattr(value, "timestamp", None)
    if callable(timestamp):
        try:
            return int(float(timestamp()) * 1000)
        except (TypeError, ValueError, OverflowError):
            return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _serialize_candidate(candidate: DecisionCandidate) -> dict[str, Any]:
    return {
        "action_type": candidate.action_type,
        "channel": candidate.channel,
        "score": float(candidate.score),
        "expected_value": float(candidate.expected_value),
        "confidence": float(candidate.confidence),
        "reasons": list(candidate.reasons),
        "payload": dict(candidate.payload),
        "candidate_id": candidate.candidate_id,
        "business_id": str(
            candidate.payload.get("business_id") or ""
        ).strip(),
    }


class CanonicalDemandDecisionBridge:
    def __init__(self, *, decision_core: object) -> None:
        self._decision_core = decision_core
        self._validator = DecisionPackageValidator()

    def _candidate_from_routing(
        self,
        routing_candidate,
        preferred_channels: dict[str, str],
    ) -> DecisionCandidate:
        business_id = str(
            getattr(routing_candidate, "business_id", "") or ""
        ).strip()
        if not business_id:
            raise ValueError("routing candidate requires business_id")
        raw_channel = str(
            preferred_channels.get(business_id)
            or DEFAULT_DELIVERY_CHANNEL
        ).strip()
        channel = raw_channel or DEFAULT_DELIVERY_CHANNEL
        trace = dict(getattr(routing_candidate, "trace", {}) or {})
        policy = DEFAULT_CANONICAL_DECISION_BRIDGE_POLICY
        adjusted = max(
            policy.minimum_score,
            coerce_float(
                trace.get(
                    "adjusted_score",
                    getattr(routing_candidate, "rank_score", 0.0),
                ),
                0.0,
            ),
        )
        match_score = max(
            policy.minimum_score,
            coerce_float(
                trace.get("match_score", adjusted),
                adjusted,
            ),
        )
        risk_score = coerce_float(
            trace.get("risk_score", 0.0),
            0.0,
            minimum=policy.minimum_score,
            maximum=policy.maximum_score,
        )
        confidence = max(
            policy.minimum_score,
            min(
                policy.maximum_score,
                policy.base_confidence
                + adjusted * policy.adjusted_confidence_weight,
            ),
        )
        return DecisionCandidate(
            action_type="route_lead",
            channel=channel,
            score=adjusted,
            expected_value=max(policy.minimum_score, adjusted),
            confidence=confidence,
            reasons=["demand_route_candidate"],
            payload={
                "business_id": business_id,
                "rank_score": adjusted,
                "match_score": match_score,
                "adjusted_score": adjusted,
                "risk_score": risk_score,
            },
            candidate_id=f"demand-route:{business_id}",
        )

    def _world_state(
        self,
        *,
        request: Any,
        request_id: str,
        candidates: list[DecisionCandidate],
        blocked_count: int,
        manual_review_reason: str,
    ) -> WorldStateV1:
        customer_id = str(
            getattr(request, "customer_id", "") or request_id
        ).strip()
        tenant_id = str(
            getattr(request, "tenant_id", "") or "demand_network"
        ).strip()
        return WorldStateV1(
            schema_version=1,
            user={"customer_id": customer_id},
            session={
                "request_id": request_id,
                "intent": "demand_route",
            },
            product={
                "product_id": "demand_network",
                "domain": "demand_routing",
                "product_version": "v1",
                "tenant_id": tenant_id,
            },
            economy={},
            timestamp_ms=_request_timestamp_ms(request),
            tenant_id=tenant_id,
            user_id=customer_id,
            meta={
                "purpose": "demand_route",
                "demand_route": {
                    "request_id": request_id,
                    "candidates": [
                        _serialize_candidate(candidate)
                        for candidate in candidates
                    ],
                    "constraints": asdict(DecisionConstraints()),
                    "blocked_candidate_count": int(blocked_count),
                    "manual_review_reason": manual_review_reason,
                },
            },
        )

    def _issue_route_decision(self, *, state: WorldStateV1):
        return issue_runtime_decision(
            issuer=self._decision_core,
            state=state,
        )

    def evaluate(self, *, request, routing_preparation) -> RoutingDecision:
        return self.issue(
            request=request,
            routing_preparation=routing_preparation,
        )

    decide = evaluate

    def issue(self, *, request, routing_preparation) -> RoutingDecision:
        prepared = dict(routing_preparation)
        request_id = str(getattr(request, "request_id", "") or "")
        if not request_id:
            raise ValueError("request requires request_id")
        prepared.setdefault("request_id", request_id)
        package = self._validator.validate(prepared)
        if str(package.get("request_id") or "") != request_id:
            raise ValueError(
                "routing preparation request_id must match request"
            )

        ranked = tuple(package.get("ranked_candidates") or ())
        trace = dict(package.get("trace") or {})
        preferred_channels = {
            str(key).strip(): (
                str(value).strip() or DEFAULT_DELIVERY_CHANNEL
            )
            for key, value in dict(
                trace.get("preferred_channels") or {}
            ).items()
            if str(key).strip()
        }
        seen_business_ids: set[str] = set()
        candidates: list[DecisionCandidate] = []
        blocked_count = 0
        for candidate in ranked:
            if getattr(candidate, "blocked", False):
                blocked_count += 1
                continue
            business_id = str(
                getattr(candidate, "business_id", "") or ""
            ).strip()
            if not business_id or business_id in seen_business_ids:
                continue
            seen_business_ids.add(business_id)
            candidates.append(
                self._candidate_from_routing(
                    candidate,
                    preferred_channels,
                )
            )

        manual_review_reason = str(
            trace.get("manual_review_reason") or "no_safe_candidates"
        )
        state = self._world_state(
            request=request,
            request_id=request_id,
            candidates=candidates,
            blocked_count=blocked_count,
            manual_review_reason=manual_review_reason,
        )
        envelope = self._issue_route_decision(state=state)
        decision = getattr(envelope, "decision", None)
        if decision is None:
            raise RuntimeError("demand_route_envelope_missing_decision")
        if str(getattr(decision, "action", "")) != ACTION_ROUTE_LEAD_V1:
            raise RuntimeError("demand_route_unexpected_action")
        payload = dict(getattr(decision, "payload", {}) or {})

        selected_business_id = str(
            payload.get("selected_business_id") or ""
        ).strip() or None
        runner_ups = tuple(
            str(item).strip()
            for item in payload.get("runner_up_business_ids") or ()
            if str(item).strip()
        )[:MAX_RUNNER_UPS]

        decision_trace = dict(trace)
        decision_trace["decision_path"] = CANONICAL_DECISION_PATH
        decision_trace["optimization_target"] = str(
            trace.get("optimization_target")
            or CANONICAL_OPTIMIZATION_TARGET
        )
        decision_trace["decision_id"] = str(
            getattr(decision, "decision_id", "") or ""
        )
        decision_trace["request_id"] = request_id
        decision_trace["selected_from_candidates"] = int(
            payload.get("candidate_count") or 0
        )
        decision_trace["blocked_candidate_count"] = int(
            payload.get("blocked_candidate_count") or blocked_count
        )
        if selected_business_id is None:
            decision_trace["manual_review_reason"] = str(
                payload.get("manual_review_reason")
                or manual_review_reason
            )
        else:
            decision_trace["delivery_channel"] = str(
                payload.get("delivery_channel")
                or preferred_channels.get(selected_business_id)
                or DEFAULT_DELIVERY_CHANNEL
            )

        return RoutingDecision(
            request_id=request_id,
            selected_business_id=selected_business_id,
            runner_up_business_ids=runner_ups,
            trace=decision_trace,
            requires_manual_review=bool(
                payload.get(
                    "requires_manual_review",
                    selected_business_id is None,
                )
            ),
        )
