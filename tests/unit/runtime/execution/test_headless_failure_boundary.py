from __future__ import annotations

from types import SimpleNamespace

from application.autonomy import autonomy_execution_step as execution_step_module
from application.autonomy.autonomy_execution_step import AutonomyExecutionStep
from runtime.execution.execution_contract_lock import ExecutionContractLockError
from runtime.execution.outcome_persistence_lock import finalize_failed_outcome


class _SafetyVerdict:
    allowed = True
    operator_required = False
    reason = "ok"
    details: dict[str, object] = {}

    @staticmethod
    def to_dict() -> dict[str, object]:
        return {"allowed": True, "operator_required": False, "reason": "ok", "details": {}}


class _AuditRecord:
    @staticmethod
    def to_dict() -> dict[str, object]:
        return {"status": "recorded"}


class _SafetyBundle:
    @staticmethod
    def evaluate_pre_execution(**_kwargs) -> _SafetyVerdict:
        return _SafetyVerdict()

    @staticmethod
    def build_policy_snapshot(**_kwargs) -> dict[str, object]:
        return {"status": "sealed"}

    @staticmethod
    def build_audit_record(**_kwargs) -> _AuditRecord:
        return _AuditRecord()


class _KeywordOnlyOutbox:
    def __init__(self) -> None:
        self.dead_letters: list[dict[str, str]] = []

    def move_to_dead_letter(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        error: str,
    ) -> None:
        self.dead_letters.append(
            {
                "tenant_id": tenant_id,
                "message_id": message_id,
                "owner_id": owner_id,
                "error": error,
            }
        )


def test_headless_verification_lock_becomes_failed_operator_step(monkeypatch) -> None:
    contract = SimpleNamespace(
        _autonomy_safety_bundle=_SafetyBundle(),
        _executor=object(),
        _event_log=None,
    )
    step = AutonomyExecutionStep(contract=contract)
    envelope = SimpleNamespace(
        decision=SimpleNamespace(decision_id="decision-1", correlation_id="correlation-1")
    )
    monkeypatch.setattr(step, "_finalize_execution_envelope", lambda **_kwargs: envelope)
    monkeypatch.setattr(
        execution_step_module,
        "execute_headless_envelope",
        lambda **_kwargs: (_ for _ in ()).throw(ExecutionContractLockError("unverified")),
    )

    result = step.execute(
        request=SimpleNamespace(meta={}, autonomy_tier="supervised"),
        executable_action=SimpleNamespace(payload={}, action_type="send_message@v1"),
        envelope=envelope,
        autonomy_decision=SimpleNamespace(
            blocked_by_policy=False,
            approval_required=False,
        ),
    )

    assert result.ok is False
    assert result.error == "execution_contract:unverified"
    assert result.output["attempted"] is True
    assert result.output["executed"] is False
    assert result.output["verified"] is False
    assert result.output["operator_required"] is True


def test_failed_outcome_uses_canonical_dead_letter_adapter_signature() -> None:
    outbox = _KeywordOnlyOutbox()
    executor = SimpleNamespace(_outbox=outbox, _reliability=None)
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-2",
            action="send_message@v1",
            payload={"tenant_id": "tenant-2"},
        )
    )

    result = finalize_failed_outcome(
        executor=executor,
        env=env,
        reason="DECISION_EXPIRED",
        output={"status": "failed"},
    )

    assert outbox.dead_letters == [
        {
            "tenant_id": "tenant-2",
            "message_id": "decision-2",
            "owner_id": "runtime-executor",
            "error": "DECISION_EXPIRED",
        }
    ]
    assert result["state_update"]["outbox_state"] == "dead_letter"
    assert result["evidence_record"]["reason"] == "DECISION_EXPIRED"
