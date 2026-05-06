from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from boot.registrations._shared import register_runtime_singleton
from config.decision_safety_policy import (
    DEFAULT_REWARD_GUARD_POLICY_DEFAULTS,
    DEFAULT_RISK_SCORER_POLICY,
    DEFAULT_SAFETY_PROFILE_POLICY,
)
from runtime.audit_log import RuntimeAuditLog
from runtime.registry import RuntimeRegistry
from runtime.runtime_observability import RuntimeObservability
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value or '').strip().lower()
    return token in {'1', 'true', 'yes', 'y', 'on'}


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _payload(action: object) -> dict[str, Any]:
    if isinstance(action, Mapping):
        return dict(action)
    payload = getattr(action, 'payload', None)
    if isinstance(payload, Mapping):
        body = dict(payload)
        body.setdefault('action_type', str(getattr(action, 'action_type', '') or ''))
        return body
    return {}


@dataclass
class ActionBudget:
    max_actions: int = DEFAULT_SAFETY_PROFILE_POLICY.action_budget_max_actions

    def allow(self, planned_actions: int | Mapping[str, Any] | object) -> bool:
        if isinstance(planned_actions, int):
            count = max(0, int(planned_actions))
        else:
            body = _payload(planned_actions)
            count = max(
                1,
                _safe_int(
                    body.get('planned_actions', body.get('action_count', body.get('recipient_count', 1))),
                    default=1,
                ),
            )
            recipients = body.get('recipients')
            if isinstance(recipients, (list, tuple, set, frozenset)) and recipients:
                count = max(count, len(recipients))
        return count <= self.max_actions


@dataclass
class KillSwitch:
    is_stopped: bool = False

    def allow(self) -> bool:
        return not self.is_stopped


@dataclass
class RewardGuard:
    min_reward: float = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.min_reward
    min_margin: float = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.min_margin

    def validate(self, action: object) -> bool:
        body = _payload(action)
        if _safe_bool(body.get('reward_hacking_detected')):
            return False
        if _safe_bool(body.get('blocked_by_policy')):
            return False
        reward = _safe_float(body.get('expected_reward', body.get('reward', 0.0)))
        margin = _safe_float(body.get('expected_margin', body.get('margin', 0.0)))
        return reward >= self.min_reward and margin >= self.min_margin


@dataclass
class RiskEngine:
    default_high_risk_score: float = DEFAULT_RISK_SCORER_POLICY.amount_risk_increment + DEFAULT_RISK_SCORER_POLICY.review_flag_risk_increment + 0.15
    elevated_risk_score: float = DEFAULT_RISK_SCORER_POLICY.amount_risk_increment + 0.20

    def score(self, action: object) -> float:
        body = _payload(action)
        value = body.get('risk_score')
        if value not in (None, ''):
            score = _safe_float(value)
        elif _safe_bool(body.get('high_risk')):
            score = self.default_high_risk_score
        elif _safe_bool(body.get('requires_human_approval')):
            score = self.elevated_risk_score
        else:
            score = 0.0
        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        return score


@dataclass
class SimulationGate:
    def allow(self, action: object) -> bool:
        body = _payload(action)
        if _safe_bool(body.get('requires_simulation')) and not _safe_bool(body.get('simulation_passed')):
            return False
        if 'simulation_safe' in body and not _safe_bool(body.get('simulation_safe')):
            return False
        return True


def build_runtime_observability() -> RuntimeObservability:
    return RuntimeObservability(audit_log=RuntimeAuditLog())


def register_observability(registry: RuntimeRegistry):
    return register_runtime_singleton(
        registry,
        name=RuntimeServiceName.OBSERVABILITY,
        service_builder=build_runtime_observability,
        service_type=RuntimeServiceType.GUARD,
    )


def register_risk(registry: RuntimeRegistry):
    return register_runtime_singleton(
        registry,
        name=RuntimeServiceName.RISK_ENGINE,
        service_builder=RiskEngine,
        service_type=RuntimeServiceType.GUARD,
    )


def register_reward(registry: RuntimeRegistry):
    return register_runtime_singleton(
        registry,
        name=RuntimeServiceName.REWARD_GUARD,
        service_builder=RewardGuard,
        service_type=RuntimeServiceType.GUARD,
    )


def register_simulation(registry: RuntimeRegistry):
    return register_runtime_singleton(
        registry,
        name=RuntimeServiceName.SIMULATION_GATE,
        service_builder=SimulationGate,
        service_type=RuntimeServiceType.GUARD,
    )


def register_kill_switch(registry: RuntimeRegistry):
    return register_runtime_singleton(
        registry,
        name=RuntimeServiceName.KILL_SWITCH,
        service_builder=KillSwitch,
        service_type=RuntimeServiceType.GUARD,
    )


def register_action_budget(registry: RuntimeRegistry):
    return register_runtime_singleton(
        registry,
        name=RuntimeServiceName.ACTION_BUDGET,
        service_builder=ActionBudget,
        service_type=RuntimeServiceType.GUARD,
    )


__all__ = [
    'ActionBudget',
    'KillSwitch',
    'RewardGuard',
    'RiskEngine',
    'SimulationGate',
    'build_runtime_observability',
    'register_action_budget',
    'register_kill_switch',
    'register_observability',
    'register_reward',
    'register_risk',
    'register_simulation',
]
