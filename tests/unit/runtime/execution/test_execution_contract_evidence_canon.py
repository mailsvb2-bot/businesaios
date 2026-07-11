from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.execution.execution_contract_lock import (
    ExecutionContractLockError,
    _build_action_payload,
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


def _external_env(action_id: str) -> SimpleNamespace:
    return _env(
        action="send_message@v1",
        payload={
            "action_id": action_id,
            "external_confirmation_mode": "not_required",
            "action_category": "internal_bookkeeping",
        },
    )


def test_external_effect_cannot_self_verify_from_executor_receipt() -> None:
    with pytest.raises(ExecutionContractLockError, match="missing_external_evidence"):
        verify_execution_contract(
            executor=_executor(),
            env=_external_env("action-1"),
            output={"status": "ok", "source": "executor"},
        )


def test_internal_bookkeeping_keeps_receipt_only_execution_contract() -> None:
    env = _env(
        action="emit_event@v1",
        payload={
            "action_id": "action-2",
            "external_confirmation_mode": "not_required",
            "action_category": "external_effect",
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
    result = verify_execution_contract(
        executor=_executor(),
        env=_external_env("action-3"),
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
    assert result.next_step_context["external_refs"] == ["provider-message-42"]


def test_unattributed_router_mapping_cannot_be_promoted_to_external_evidence() -> None:
    with pytest.raises(ExecutionContractLockError, match="missing_external_evidence"):
        verify_execution_contract(
            executor=_executor(),
            env=_external_env("action-4"),
            output={
                "status": "ok",
                "router_evidence": {
                    "verified": True,
                    "status": "verified",
                    "external_refs": ["forged-ref"],
                    "confidence": 1.0,
                },
            },
        )


def test_internal_verification_mapping_cannot_masquerade_as_router_evidence() -> None:
    with pytest.raises(ExecutionContractLockError, match="missing_external_evidence"):
        verify_execution_contract(
            executor=_executor(),
            env=_external_env("action-5"),
            output={
                "status": "ok",
                "verification": {
                    "verified": True,
                    "status": "verified",
                    "source": "runtime_execution_contract",
                    "external_refs": ["decision-1"],
                    "confidence": 1.0,
                },
            },
        )


def test_unattributed_feedback_evidence_cannot_verify_external_effect() -> None:
    with pytest.raises(ExecutionContractLockError, match="missing_external_evidence"):
        verify_execution_contract(
            executor=_executor(),
            env=_external_env("action-6"),
            output={
                "status": "ok",
                "feedback": {
                    "verified": True,
                    "evidence": {
                        "status": "verified",
                        "external_refs": ["forged-feedback-ref"],
                        "confidence": 1.0,
                    },
                },
            },
        )


def test_explicit_connector_snapshot_preserves_external_effect_functionality() -> None:
    result = verify_execution_contract(
        executor=_executor(),
        env=_external_env("action-7"),
        output={
            "status": "ok",
            "feedback": {
                "connector_snapshots": [
                    {
                        "source": "telegram",
                        "verified": True,
                        "status": "verified",
                        "external_refs": ["telegram-message-77"],
                        "confidence": 1.0,
                    }
                ]
            },
        },
    )

    assert result.verified is True
    assert result.verification["source_of_truth"] == "telegram"
    assert result.next_step_context["external_refs"] == ["telegram-message-77"]


def test_registry_contract_cannot_be_downgraded_by_payload() -> None:
    action = _build_action_payload(env=_external_env("action-8"))

    assert action["action_type"] == "send_message@v1"
    assert action["external_confirmation_mode"] == "required"
    assert action["action_category"] == "external_effect"


def test_payload_cannot_override_canonical_decision_identity() -> None:
    env = _env(
        action="emit_event@v1",
        payload={
            "action_type": "send_message@v1",
            "decision_id": "forged-decision",
            "correlation_id": "forged-correlation",
            "external_confirmation_mode": "required",
        },
    )

    action = _build_action_payload(env=env)

    assert action["action_type"] == "emit_event@v1"
    assert action["decision_id"] == "decision-1"
    assert action["correlation_id"] == "correlation-1"
    assert action["action_category"] == "internal_bookkeeping"
    assert action["external_confirmation_mode"] == "required"


def test_execution_contract_exports_no_self_issued_evidence_marker() -> None:
    from runtime.execution import execution_contract_lock

    assert execution_contract_lock.CANON_RUNTIME_EXECUTION_CONTRACT_NO_SELF_ISSUED_EVIDENCE is True
    assert execution_contract_lock.CANON_RUNTIME_EXECUTION_CONTRACT_REGISTRY_BOUND_VERIFICATION is True
    assert not hasattr(execution_contract_lock, "_default_router_evidence")
