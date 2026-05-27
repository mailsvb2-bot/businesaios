from __future__ import annotations

import json
from dataclasses import dataclass

from application.headless.feedback import SimpleHeadlessFeedbackReader
from application.headless.goal_mapper import HeadlessGoalStateMapper
from application.headless.stop_policy import HeadlessStopPolicy
from core.ai.decision import Decision, DecisionEnvelope
from execution.headless_contract import GoalExecutionRequest, HeadlessExecutionContract
from execution.operator_handoff import FileOperatorHandoffStore
from runtime.execution.executor_result import ExecutionResult


@dataclass
class StubDecisionCore:
    action: str

    def optimize(self, state):
        return DecisionEnvelope(
            decision=Decision(
                decision_id='dec-tier',
                issuer_id='businesaios-core',
                issued_at_ms=1,
                expires_at_ms=2,
                policy_id='policy-tier',
                action=self.action,
                payload={'feedback_seed': {'terminal': True, 'goal_reached': True}},
                snapshot_id='snap-1',
                state_hash='hash-1',
                correlation_id='corr-tier',
                state_schema_version=1,
                action_schema_version=1,
            ),
            payload_hash='hash',
            signature='sig',
            kid='kid',
        )


@dataclass
class RecordingExecutor:
    calls: int = 0

    def execute(self, env):
        self.calls += 1
        return ExecutionResult(
            ok=True,
            output={
                'goal_reached': True,
                'terminal': True,
                'effector': {'verified': True, 'external_ref': 'ext-1', 'evidence': {'external_refs': ['ext-1']}},
            },
            error=None,
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
        )


def test_supervised_tier_requires_handoff_and_skips_execution(tmp_path) -> None:
    executor = RecordingExecutor()
    handoff = FileOperatorHandoffStore(root_dir=tmp_path / 'handoff')
    contract = HeadlessExecutionContract(
        decision_core=StubDecisionCore(action='launch_campaign'),
        executor=executor,
        state_mapper=HeadlessGoalStateMapper(),
        feedback_reader=SimpleHeadlessFeedbackReader.default(),
        stop_policy=HeadlessStopPolicy(max_failures=1),
        operator_handoff_store=handoff,
    )
    report = contract.execute_autopilot(
        GoalExecutionRequest(goal='launch ads', business_id='biz-1', tenant_id='tenant-1', autonomy_tier='supervised')
    )
    assert executor.calls == 0
    assert report.completed is False
    assert report.steps[0].status == 'approval_required'
    record = json.loads(handoff.list_records()[0].read_text(encoding='utf-8'))
    assert record['approval_required'] is True
    assert record['autonomy_tier'] == 'supervised'


def test_bounded_autonomy_blocks_ads_launch(tmp_path) -> None:
    executor = RecordingExecutor()
    contract = HeadlessExecutionContract(
        decision_core=StubDecisionCore(action='launch_campaign'),
        executor=executor,
        state_mapper=HeadlessGoalStateMapper(),
        feedback_reader=SimpleHeadlessFeedbackReader.default(),
        stop_policy=HeadlessStopPolicy(max_failures=1),
    )
    report = contract.execute_autopilot(
        GoalExecutionRequest(goal='launch ads', business_id='biz-1', tenant_id='tenant-1', autonomy_tier='bounded_autonomy')
    )
    assert executor.calls == 0
    assert report.steps[0].status == 'blocked_by_policy'
    assert report.final_feedback['blocked_by_policy'] is True
