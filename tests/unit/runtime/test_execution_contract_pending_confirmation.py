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


def test_external_effect_without_independent_evidence_remains_fail_closed() -> None:
    with pytest.raises(ExecutionContractLockError, match="missing_external_evidence"):
        verify_execution_contract(
            executor=SimpleNamespace(_reliability=None),
            env=_env(),
            output={"ok": True, "status": "executed"},
        )


def test_trusted_provider_acknowledgement_verifies_external_effect() -> None:
    result = verify_execution_contract(
        executor=SimpleNamespace(_reliability=None),
        env=_env(),
        output={
            "ok": True,
            "status": "executed",
            "evidence": {
                "source": "payment_gateway",
                "verified": True,
                "status": "verified",
                "external_refs": ["payment:test"],
                "confidence": 1.0,
            },
        },
    )

    assert result.verified is True
    assert result.next_step_context["external_outcome_verified"] is True
    assert result.next_step_context["external_refs"] == ["payment:test"]


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
