from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.execution.execution_contract_lock import (
    ExecutionContractLockError,
    verify_execution_contract,
)


def _env(*, action: str, payload: dict[str, object]) -> SimpleNamespace:
    decision = SimpleNamespace(
        decision_id="decision-1",
        correlation_id="correlation-1",
        action=action,
        payload=dict(payload),
        issued_at_ms=1_750_000_000_000,
    )
    return SimpleNamespace(decision=decision)


def _executor() -> SimpleNamespace:
    return SimpleNamespace(_evidence_verifier=None, _reliability=None)


def test_external_effect_cannot_self_verify_from_executor_receipt() -> None:
    env = _env(
        action="send_message",
        payload={
            "action_id": "action-1",
            "external_confirmation_mode": "required",
            "action_category": "write",
        },
    )

    with pytest.raises(ExecutionContractLockError, match="missing_external_evidence"):
        verify_execution_contract(
            executor=_executor(),
            env=env,
            output={"status": "ok", "source": "executor"},
        )


def test_internal_bookkeeping_keeps_receipt_only_execution_contract() -> None:
    env = _env(
        action="record_internal_checkpoint",
        payload={
            "action_id": "action-2",
            "external_confirmation_mode": "not_required",
            "action_category": "internal_bookkeeping",
        },
    )

    result = verify_execution_contract(
        executor=_executor(),
        env=env,
        output={"status": "ok", "source": "executor"},
    )

    assert result.verified is True
    assert result.verification["status"] == "verified"
    assert result.verification["source_of_truth"] == "executor"


def test_external_effect_accepts_observable_router_evidence() -> None:
    env = _env(
        action="send_message",
        payload={
            "action_id": "action-3",
            "external_confirmation_mode": "required",
            "action_category": "write",
        },
    )

    result = verify_execution_contract(
        executor=_executor(),
        env=env,
        output={
            "status": "ok",
            "source": "executor",
            "router_evidence": {
                "verified": True,
                "status": "verified",
                "code": "provider_acknowledged",
                "source": "effect_router",
                "external_refs": ["provider-message-42"],
                "confidence": 1.0,
            },
        },
    )

    assert result.verified is True
    assert result.verification["status"] == "verified"
    assert result.verification["source_of_truth"] == "router"
    assert "provider-message-42" in result.verification["external_refs"]


def test_execution_contract_exports_no_self_issued_evidence_marker() -> None:
    from runtime.execution import execution_contract_lock

    assert execution_contract_lock.CANON_RUNTIME_EXECUTION_CONTRACT_NO_SELF_ISSUED_EVIDENCE is True
    assert not hasattr(execution_contract_lock, "_default_router_evidence")
