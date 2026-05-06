from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from execution.action_capability_matrix import get_action_capability
from execution.routing.capability_cost_model import CapabilityCostModel
from execution.routing.capability_latency_model import CapabilityLatencyModel
from execution.routing.capability_probe import CapabilityProbe
from execution.routing.capability_proofability_score import CapabilityProofabilityScore
from execution.routing.capability_quarantine import CapabilityQuarantine
from execution.routing.route_continuity_memory import RouteContinuityMemory
from execution.routing.capability_registry import CapabilityRegistry, CapabilityRoute
from execution.routing.fallback_tree import FallbackTree
from execution.routing.route_explainer import RouteExplanation
from config.decision_safety_policy import DEFAULT_CAPABILITY_ROUTING_POLICY
CANON_CAPABILITY_ROUTER = True
def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
@dataclass(frozen=True)
class RoutingDecision:
    selected_route: CapabilityRoute | None
    alternatives: tuple[CapabilityRoute, ...]
    explanation: RouteExplanation
    score_breakdown: dict[str, dict[str, float]]
    def to_dict(self) -> dict[str, Any]:
        return {
            'selected_route': None if self.selected_route is None else self.selected_route.route_key,
            'alternatives': [item.route_key for item in self.alternatives],
            'explanation': self.explanation.to_dict(),
            'score_breakdown': {key: dict(value) for key, value in self.score_breakdown.items()},
        }
class CapabilityRouter:
    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        quarantine: CapabilityQuarantine | None = None,
        cost_model: CapabilityCostModel | None = None,
        latency_model: CapabilityLatencyModel | None = None,
        proofability_score: CapabilityProofabilityScore | None = None,
        fallback_tree: FallbackTree | None = None,
    ) -> None:
        self._registry = registry
        self._quarantine = quarantine or CapabilityQuarantine()
        self._cost_model = cost_model or CapabilityCostModel()
        self._latency_model = latency_model or CapabilityLatencyModel()
        self._proofability_score = proofability_score or CapabilityProofabilityScore()
        self._fallback_tree = fallback_tree or FallbackTree()
        self._probe = CapabilityProbe(quarantine=self._quarantine)
        self._continuity_memory = RouteContinuityMemory()
        self._policy = DEFAULT_CAPABILITY_ROUTING_POLICY
    def _maturity_score(self, route: CapabilityRoute) -> float:
        policy = self._policy
        mapping = {
            'real': policy.maturity_score_real,
            'capability_shell': policy.maturity_score_shell,
            'placeholder': policy.maturity_score_placeholder,
        }
        return float(mapping.get(str(route.maturity), policy.maturity_score_default))
    def _route_score(
        self,
        *,
        route: CapabilityRoute,
        requested_units: float,
        externally_verified: bool,
        prod_ready: bool,
        continuity_bonus: float = 0.0,
    ) -> dict[str, float]:
        health = max(0.0, min(1.0, float(route.health_score)))
        cost = self._cost_model.score(route=route, requested_units=requested_units)
        latency = self._latency_model.score(route=route)
        proofability = self._proofability_score.score(
            route=route,
            externally_verified=externally_verified,
            prod_ready=prod_ready,
        )
        policy = self._policy
        maturity = self._maturity_score(route)
        bounded_continuity_bonus = max(0.0, min(policy.continuity_bonus_cap, float(continuity_bonus)))
        total = (
            health * policy.weight_health
            + proofability * policy.weight_proofability
            + latency * policy.weight_latency
            + cost * policy.weight_cost
            + maturity * policy.weight_maturity
            + bounded_continuity_bonus
        )
        return {
            'health': health,
            'proofability': proofability,
            'latency': latency,
            'cost': cost,
            'maturity': maturity,
            'continuity_bonus': bounded_continuity_bonus,
            'total': total,
        }
    def select_best_route(
        self,
        *,
        capability_key: str,
        action_type: str,
        requested_units: float = 1.0,
        runtime_routes: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> RoutingDecision:
        action_cap = get_action_capability(action_type)
        if not bool(action_cap.executable):
            explanation = RouteExplanation(
                selected_route_key=None,
                summary='action is not executable',
                factors={'capability_key': capability_key, 'action_type': action_type, 'reason': 'action_not_executable'},
            )
            return RoutingDecision(None, (), explanation, {})
        if not bool(action_cap.routable):
            explanation = RouteExplanation(
                selected_route_key=None,
                summary='action is not routable',
                factors={'capability_key': capability_key, 'action_type': action_type, 'reason': 'action_not_routable'},
            )
            return RoutingDecision(None, (), explanation, {})
        candidates = self._registry.routes_for(capability_key=capability_key, action_type=action_type)
        runtime_payload = _safe_dict(runtime_routes)
        if not candidates:
            explanation = RouteExplanation(
                selected_route_key=None,
                summary='no capability route candidates',
                factors={'capability_key': capability_key, 'action_type': action_type},
            )
            return RoutingDecision(None, (), explanation, {})
        score_breakdown: dict[str, dict[str, float]] = {}
        rejected: dict[str, str] = {}
        available: list[CapabilityRoute] = []
        for route in candidates:
            runtime_info = _safe_dict(runtime_payload.get(route.route_key))
            effective_route = route
            if runtime_info:
                enabled = runtime_info.get('enabled', route.enabled)
                effective_route = CapabilityRoute(
                    route_key=route.route_key,
                    capability_key=route.capability_key,
                    supported_action_types=route.supported_action_types,
                    maturity=route.maturity,
                    enabled=bool(enabled),
                    base_cost=float(runtime_info.get('base_cost', route.base_cost) or route.base_cost),
                    base_latency_ms=float(runtime_info.get('base_latency_ms', route.base_latency_ms) or route.base_latency_ms),
                    base_proofability=float(runtime_info.get('base_proofability', route.base_proofability) or route.base_proofability),
                    health_score=float(runtime_info.get('health_score', route.health_score) or 0.0),
                    metadata={**dict(route.metadata), 'runtime': runtime_info},
                )
                if runtime_info.get('healthy') is False and effective_route.health_score >= self._policy.unhealthy_health_cap:
                    effective_route = CapabilityRoute(
                        route_key=effective_route.route_key,
                        capability_key=effective_route.capability_key,
                        supported_action_types=effective_route.supported_action_types,
                        maturity=effective_route.maturity,
                        enabled=effective_route.enabled,
                        base_cost=effective_route.base_cost,
                        base_latency_ms=effective_route.base_latency_ms,
                        base_proofability=effective_route.base_proofability,
                        health_score=min(effective_route.health_score, self._policy.unhealthy_health_cap),
                        metadata=dict(effective_route.metadata),
                    )
            probe = self._probe.probe(route=effective_route)
            if not probe.available:
                rejected[effective_route.route_key] = probe.reason
                continue
            if effective_route.maturity == 'placeholder':
                rejected[effective_route.route_key] = 'placeholder_not_selectable'
                continue
            continuity_signal = self._continuity_memory.read(
                route_key=effective_route.route_key,
                runtime_info=runtime_info,
            )
            available.append(effective_route)
            score_breakdown[effective_route.route_key] = self._route_score(
                route=effective_route,
                requested_units=requested_units,
                externally_verified=bool(action_cap.externally_verified),
                prod_ready=bool(action_cap.prod_ready),
                continuity_bonus=continuity_signal.advisory_bonus(),
            )
            score_breakdown[effective_route.route_key]['continuity'] = continuity_signal.to_dict()
        if not available:
            explanation = RouteExplanation(
                selected_route_key=None,
                summary='all routes unavailable after health, quarantine, and maturity filtering',
                factors={
                    'capability_key': capability_key,
                    'action_type': action_type,
                    'rejected_routes': dict(rejected),
                },
            )
            return RoutingDecision(None, (), explanation, score_breakdown)
        ranked = sorted(available, key=lambda item: score_breakdown[item.route_key]['total'], reverse=True)
        selected = ranked[0]
        alternatives = self._fallback_tree.next_candidates(routes=tuple(ranked), selected_route_key=selected.route_key)
        explanation = RouteExplanation(
            selected_route_key=selected.route_key,
            summary='best route selected by weighted health, proofability, latency, cost, and maturity',
            factors={
                'capability_key': capability_key,
                'action_type': action_type,
                'selected_total_score': score_breakdown[selected.route_key]['total'],
                'selected_continuity_bonus': score_breakdown[selected.route_key].get('continuity_bonus', 0.0),
                'rejected_routes': dict(rejected),
            },
        )
        return RoutingDecision(selected, alternatives, explanation, score_breakdown)
