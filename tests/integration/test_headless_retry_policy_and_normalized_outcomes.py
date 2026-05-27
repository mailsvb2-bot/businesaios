from __future__ import annotations

from dataclasses import dataclass

from application.effects.effect_journal import FileEffectJournal
from application.headless.feedback import SimpleHeadlessFeedbackReader
from application.headless.goal_mapper import HeadlessGoalStateMapper
from application.headless.stop_policy import HeadlessStopPolicy
from application.learning.retry_taxonomy import RetryTaxonomy
from core.ai.decision import Decision, DecisionEnvelope
from execution.goal_score import GoalScoreEngine
from execution.headless_contract import GoalExecutionRequest, HeadlessExecutionContract
from execution.headless_ledger import FileHeadlessLedger
from execution.headless_state_store import FileHeadlessStateStore
from execution.idempotency_guard import FileIdempotencyGuard
from execution.outcome_normalizer import OutcomeNormalizer
from execution.policy_explainer import PolicyExplainer
from runtime.execution.executor_result import ExecutionResult


@dataclass
class StubDecisionCore:
    def optimize(self, state):
        return DecisionEnvelope(
            decision=Decision(
                decision_id="dec-retry",
                issuer_id="businesaios-core",
                issued_at_ms=1,
                expires_at_ms=2,
                policy_id="policy-77",
                action="notify_owner",
                payload={"feedback_seed": {"converted": True}},
                snapshot_id="snap-1",
                state_hash="hash-1",
                correlation_id="corr-retry",
                state_schema_version=1,
                action_schema_version=1,
            ),
            payload_hash="hash",
            signature="sig",
            kid="kid",
        )


@dataclass
class StubExecutor:
    def execute(self, env):
        return ExecutionResult(
            ok=False,
            output={"revenue": "40", "responded": 1},
            error="timeout",
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
        )


def test_contract_emits_retry_and_normalized_outcome_metadata(tmp_path) -> None:
    contract = HeadlessExecutionContract(
        decision_core=StubDecisionCore(),
        executor=StubExecutor(),
        state_mapper=HeadlessGoalStateMapper(),
        feedback_reader=SimpleHeadlessFeedbackReader(),
        stop_policy=HeadlessStopPolicy(max_failures=1),
        ledger=FileHeadlessLedger(root_dir=tmp_path / "ledger"),
        state_store=FileHeadlessStateStore(root_dir=tmp_path / "state"),
        effect_journal=FileEffectJournal(root_dir=tmp_path / "effects"),
        idempotency_guard=FileIdempotencyGuard(root_dir=tmp_path / "idem"),
        goal_score_engine=GoalScoreEngine(),
        retry_taxonomy=RetryTaxonomy(),
        policy_explainer=PolicyExplainer(),
        outcome_normalizer=OutcomeNormalizer(),
    )

    report = contract.execute_autopilot(
        GoalExecutionRequest(
            goal="process inbound leads",
            business_id="biz-1",
            tenant_id="tenant-1",
            max_steps=2,
        )
    )

    assert report.completed is False
    assert report.stop_reason == "execution_failed"
    step_feedback = report.steps[0].feedback
    assert step_feedback["retry_classification"]["kind"] == "recoverable"
    assert step_feedback["retry_classification"]["should_retry"] is True
    assert step_feedback["normalized_outcome"]["revenue"] == 40.0
    assert step_feedback["normalized_outcome"]["responded"] is True
    assert step_feedback["policy_explanation"]["policy_id"] == "policy-77"
