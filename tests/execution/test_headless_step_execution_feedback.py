from application.headless.step_builder import HeadlessStepBuilder
from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction


def test_headless_step_builder_attaches_canonical_execution_feedback() -> None:
    step = HeadlessStepBuilder().build(
        step_index=0,
        action=ExecutableAction(
            action_id="act-1",
            decision_id="dec-1",
            correlation_id="corr-1",
            action_type="telegram.send_message",
            channel="telegram",
            payload={"chat_id": "1"},
            objective_name="notify",
        ),
        action_result=ActionResult(
            action_id="act-1",
            status="executed",
            message="ok",
            payload={"attempted": True, "executed": True, "verified": False, "operator_required": False},
        ),
        feedback={
            "attempted": True,
            "executed": True,
            "verified": True,
            "verification_status": "verified",
            "external_refs": ["proof://1"],
        },
    )
    assert step.execution_feedback["action_type"] == "telegram.send_message"
    assert step.execution_feedback["verification_status"] == "verified"
    assert step.execution_feedback["external_ref"] == "proof://1"
