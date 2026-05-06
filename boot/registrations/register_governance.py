from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.constructor_tokens import is_valid_runtime_construction_token
from runtime.registry import RuntimeRegistry
from runtime.sealed_types import SealedType
from runtime.service_names import RuntimeServiceName
from boot.registrations._shared import register_runtime_service
from boot.runtime_dependency_sets import GOVERNANCE_CHAIN_DEPS
from runtime.service_types import RuntimeServiceType


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _payload(action: object) -> dict[str, Any]:
    if isinstance(action, Mapping):
        return dict(action)
    payload = getattr(action, 'payload', None)
    if isinstance(payload, Mapping):
        body = dict(payload)
        body.setdefault('action_type', str(getattr(action, 'action_type', '') or ''))
        return body
    return {}


def _max_allowed_risk(action: object) -> float:
    body = _payload(action)
    raw = body.get('max_allowed_risk_score', body.get('risk_threshold', 0.80))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.80
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@dataclass
class GovernanceChain(SealedType):
    risk_engine: object
    reward_guard: object
    simulation_gate: object
    kill_switch: object
    action_budget: object
    _construction_token: object = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_runtime_construction_token(self._construction_token):
            raise RuntimeError(
                'Illegal GovernanceChain construction. Use canonical boot factory path.'
            )

    def evaluate(self, action: object) -> bool:
        if not self.kill_switch.allow():
            return False
        if not self.reward_guard.validate(action):
            return False
        if not self.simulation_gate.allow(action):
            return False
        if not self.action_budget.allow(action):
            return False
        if self.risk_engine.score(action) > _max_allowed_risk(action):
            return False
        return True


def register_governance(registry: RuntimeRegistry):
    from boot.factories import build_governance_chain

    service = build_governance_chain(
        risk_engine=registry.get(RuntimeServiceName.RISK_ENGINE),
        reward_guard=registry.get(RuntimeServiceName.REWARD_GUARD),
        simulation_gate=registry.get(RuntimeServiceName.SIMULATION_GATE),
        kill_switch=registry.get(RuntimeServiceName.KILL_SWITCH),
        action_budget=registry.get(RuntimeServiceName.ACTION_BUDGET),
    )

    return register_runtime_service(
        registry,
        name=RuntimeServiceName.GOVERNANCE_CHAIN,
        service=service,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=GOVERNANCE_CHAIN_DEPS,
    )
