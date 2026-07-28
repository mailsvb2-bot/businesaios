from types import SimpleNamespace

import pytest

from runtime.execution.execution_contract_lock import (
    ExecutionContractLockError,
    verify_execution_contract,
)


def _env(action: str = "capture_payment@v1"):
    decision = SimpleNamespace(
        action=action,
        decision_id="decision-1",
        correlation_id="correlation-1",
        issued_at_ms=1_700_000_000_000,
        payload={"user_id": "u1", "amount": 1000, "currency": "RUB"},
    )
    return SimpleNamespace(decision=decision)


def test_successful_dispatch_is_committable_while_external_confirmation_is_pending() -> None:
    result = verify_execution_contract(
        executor=SimpleNamespace(_reliability=None),
        env=_env(),
        output={"ok": True, "status": "executed"},
    )

    assert result.verified is False
    assert result.verification["status"] == "pending"
    assert result.verification["code"] == "external_confirmation_pending"
    assert result.next_step_context["execution_verified"] is True
    assert result.next_step_context["external_outcome_verified"] is False


def test_terminal_negative_provider_evidence_remains_fail_closed() -> None:
    with pytest.raises(ExecutionContractLockError):
        verify_execution_contract(
            executor=SimpleNamespace(_reliability=None),
            env=_env(),
            output={
                "ok": True,
                "status": "executed",
                "evidence": {
                    "source": "payment_gateway",
                    "verified": False,
                    "status": "failed",
                    "external_refs": ["payment:test"],
                    "confidence": 1.0,
                },
            },
        )
