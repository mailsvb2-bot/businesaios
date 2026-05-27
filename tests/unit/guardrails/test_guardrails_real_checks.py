from __future__ import annotations

from boot.registrations.simple_singletons import RewardGuard as RuntimeRewardGuard
from boot.registrations.simple_singletons import RiskEngine, SimulationGate
from guardrails.action_budget_guard import ActionBudgetGuard
from guardrails.circuit_breaker import CircuitBreaker
from guardrails.daily_action_limit_guard import DailyActionLimitGuard
from guardrails.multi_step_approval import MultiStepApproval
from guardrails.reward_guard import RewardGuard
from guardrails.risk_score_guard import RiskScoreGuard
from guardrails.rollback_engine import RollbackEngine
from guardrails.runaway_loop_guard import RunawayLoopGuard
from guardrails.sandbox_gate import SandboxGate
from guardrails.unsafe_channel_guard import UnsafeChannelGuard


def test_guardrails_fail_closed_on_unsafe_payloads() -> None:
    assert ActionBudgetGuard(max_cost=10.0).check({'estimated_cost': 11.0}) == (False, 'action_budget_exceeded')
    assert CircuitBreaker(max_consecutive_failures=2).check({'consecutive_failures': 2}) == (False, 'circuit_open')
    assert DailyActionLimitGuard(max_actions_per_day=2).check({'daily_action_count': 2, 'planned_actions': 1}) == (False, 'daily_action_limit_exceeded')
    assert MultiStepApproval(min_approvals=2).check({'approval_required': True, 'approvals': ['a']}) == (False, 'insufficient_approvals')
    assert RewardGuard().check({'expected_reward': -1.0}) == (False, 'reward_guard_blocked')
    assert RiskScoreGuard().check({'risk_score': 0.9}) == (False, 'risk_score_blocked')
    assert RollbackEngine().check({'rollback_required': True}) == (False, 'rollback_required')
    assert RunawayLoopGuard(repetition_threshold=3).check({'action_type': 'ads_apply_budget', 'repeat_count': 3}) == (False, 'runaway_loop_detected')
    assert SandboxGate().check({'requires_sandbox': True, 'sandbox_active': False}) == (False, 'sandbox_required')
    assert UnsafeChannelGuard().check({'channel': 'sms', 'allowed_channels': ['telegram']}) == (False, 'unsafe_channel')


def test_runtime_singletons_use_real_payload_semantics() -> None:
    assert RuntimeRewardGuard().validate({'expected_reward': 0.2, 'expected_margin': 0.1}) is True
    assert RuntimeRewardGuard().validate({'reward_hacking_detected': True}) is False
    assert RiskEngine().score({'risk_score': 9}) == 1.0
    assert SimulationGate().allow({'requires_simulation': True, 'simulation_passed': False}) is False
