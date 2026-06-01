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
                decision_id="dec-evidence",
                issuer_id="businesaios-core",
                issued_at_ms=1,
                expires_at_ms=2,
                policy_id="policy-evidence",
                action="create_listing",
                payload={"feedback_seed": {"terminal": True, "goal_reached": True}},
                snapshot_id="snap-1",
                state_hash="hash-1",
                correlation_id="corr-evidence",
                state_schema_version=1,
                action_schema_version=1,
            ),
            payload_hash="hash",
            signature="sig",
            kid="kid",
        )


@dataclass
class VerifiedExecutor:
    def execute(self, env):
        return ExecutionResult(
            ok=True,
            output={
                "goal_reached": True,
                "terminal": True,
                "effector": {
                    "verified": True,
                    "status": "executed",
                    "code": "verified",
                    "message": "verified external effect",
                    "external_ref": "ext-1",
                    "evidence": {"external_refs": ["ext-1"]},
                },
            },
            error=None,
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
        )


@dataclass
class UnverifiedExecutor:
    def execute(self, env):
        return ExecutionResult(
            ok=True,
            output={
                "goal_reached": True,
                "terminal": True,
                "effector": {
                    "verified": False,
                    "status": "executed_unverified",
                    "code": "verification_missing",
                    "message": "accepted but not verified",
                    "external_ref": "ext-2",
                    "evidence": {"external_refs": ["ext-2"]},
                },
            },
            error=None,
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
        )


def _make_contract(executor) -> HeadlessExecutionContract:
    return HeadlessExecutionContract(
        decision_core=StubDecisionCore(),
        executor=executor,
        state_mapper=HeadlessGoalStateMapper(),
        feedback_reader=SimpleHeadlessFeedbackReader.default(),
        stop_policy=HeadlessStopPolicy(max_failures=1),
    )


def test_headless_goal_requires_verified_evidence() -> None:
    report = _make_contract(UnverifiedExecutor()).execute_autopilot(
        GoalExecutionRequest(goal="publish listing", business_id="biz-1", tenant_id="tenant-1", max_steps=1)
    )
    assert report.completed is False
    assert report.steps[0].verified is False
    assert report.final_feedback["evidence_status"] == "unverified"
    assert report.final_feedback["external_refs"] == ["ext-2"]


def test_headless_goal_allows_verified_evidence() -> None:
    report = _make_contract(VerifiedExecutor()).execute_autopilot(
        GoalExecutionRequest(goal="publish listing", business_id="biz-1", tenant_id="tenant-1", max_steps=1)
    )
    assert report.completed is True
    assert report.steps[0].verified is True
    assert report.steps[0].verification_status == "platforms"
    assert report.steps[0].external_ref == "ext-1"
    assert report.final_feedback["verification_confidence"] == 1.0
    assert report.final_feedback["external_refs"] == ["ext-1"]
