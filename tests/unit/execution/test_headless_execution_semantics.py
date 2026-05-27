from __future__ import annotations

from dataclasses import dataclass

from application.headless.feedback import SimpleHeadlessFeedbackReader
from application.headless.goal_mapper import HeadlessGoalStateMapper
from application.headless.stop_policy import HeadlessStopPolicy
from core.ai.decision import Decision, DecisionEnvelope
from execution.headless_contract import GoalExecutionRequest, HeadlessExecutionContract
from runtime.execution.executor_result import ExecutionResult


@dataclass
class StubDecisionCore:
    def optimize(self, state):
        return DecisionEnvelope(
            decision=Decision(
                decision_id="dec-semantics",
                issuer_id="businesaios-core",
                issued_at_ms=1,
                expires_at_ms=2,
                policy_id="policy-semantics",
                action="create_listing",
                payload={"feedback_seed": {"terminal": True, "goal_reached": True}},
                snapshot_id="snap-1",
                state_hash="hash-1",
                correlation_id="corr-semantics",
                state_schema_version=1,
                action_schema_version=1,
            ),
            payload_hash="hash",
            signature="sig",
            kid="kid",
        )


@dataclass
class AcceptedOnlyExecutor:
    def execute(self, env):
        return ExecutionResult(
            ok=True,
            output={
                "terminal": True,
                "goal_reached": True,
            },
            error=None,
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
        )


@dataclass
class VerifiedExecutor:
    def execute(self, env):
        return ExecutionResult(
            ok=True,
            output={
                "terminal": True,
                "goal_reached": True,
                "effector": {
                    "attempted": True,
                    "executed": True,
                    "verified": True,
                    "status": "executed",
                    "external_ref": "listing-verified",
                    "evidence": {"external_refs": ["listing-verified"]},
                },
            },
            error=None,
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
        )


def _make_contract(executor):
    return HeadlessExecutionContract(
        decision_core=StubDecisionCore(),
        executor=executor,
        state_mapper=HeadlessGoalStateMapper(),
        feedback_reader=SimpleHeadlessFeedbackReader.default(),
        stop_policy=HeadlessStopPolicy(max_failures=1),
    )


def test_headless_step_exposes_attempted_executed_verified_semantics() -> None:
    report = _make_contract(VerifiedExecutor()).execute_autopilot(
        GoalExecutionRequest(goal="publish listing", business_id="biz-1", tenant_id="tenant-1", max_steps=1)
    )
    step = report.steps[0]
    assert step.attempted is True
    assert step.executed is True
    assert step.verified is True
    assert step.ok is True
    assert report.final_feedback["executed"] is True
    assert report.final_feedback["verified"] is True
    assert report.executed is True
    assert report.verified is True


def test_headless_does_not_treat_plain_acceptance_as_verified_success() -> None:
    report = _make_contract(AcceptedOnlyExecutor()).execute_autopilot(
        GoalExecutionRequest(goal="publish listing", business_id="biz-1", tenant_id="tenant-1", max_steps=1)
    )
    step = report.steps[0]
    assert step.attempted is True
    assert step.executed is True
    assert step.verified is False
    assert report.completed is False
    assert report.stop_reason == "verification_failed"
    assert report.executed is True
    assert report.verified is False


def test_stop_policy_stops_on_operator_required() -> None:
    policy = HeadlessStopPolicy(max_failures=1)
    decision = policy.evaluate(
        step_index=0,
        max_steps=3,
        step_attempted=False,
        step_executed=False,
        step_verified=False,
        operator_required=True,
        feedback={"operator_required": True},
        consecutive_failures=1,
    )
    assert decision.should_stop is True
    assert decision.reason == "operator_required"


def test_stop_policy_distinguishes_execution_and_verification_failure() -> None:
    policy = HeadlessStopPolicy(max_failures=1)
    execution_failed = policy.evaluate(
        step_index=0,
        max_steps=3,
        step_attempted=True,
        step_executed=False,
        step_verified=False,
        feedback={},
        consecutive_failures=1,
    )
    verification_failed = policy.evaluate(
        step_index=0,
        max_steps=3,
        step_attempted=True,
        step_executed=True,
        step_verified=False,
        feedback={"verification_failed": True},
        consecutive_failures=1,
    )
    assert execution_failed.reason == "execution_failed"
    assert verification_failed.reason == "verification_failed"
