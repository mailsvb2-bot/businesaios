from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.experiments.hooks import _source_proof_event
from runtime.experiments.proof_semantics import resolve_action_proof_success
from runtime.proofs import ACTION_PROOF_EVENT


def test_registered_success_proof_does_not_require_boolean_flag() -> None:
    event_type = ACTION_PROOF_EVENT["noop@v1"]
    event = {
        "event_id": "proof-1",
        "source": "runtime_executor",
        "event_type": event_type,
        "decision_id": "decision-1",
        "payload": {"action": "noop@v1"},
    }
    coordinator = SimpleNamespace(
        ledger=SimpleNamespace(
            events_for_decision=lambda _decision_id, _event_type: [event]
        )
    )

    assert resolve_action_proof_success(event_type, event["payload"]) is True
    assert (
        _source_proof_event(
            coordinator,
            decision_id="decision-1",
            proof_event_type=event_type,
            ok=True,
        )
        is event
    )


def test_conflicting_explicit_proof_flags_fail_closed() -> None:
    event_type = ACTION_PROOF_EVENT["noop@v1"]
    payload = {"success": True, "ok": False}

    assert resolve_action_proof_success(event_type, payload) is None

    coordinator = SimpleNamespace(
        ledger=SimpleNamespace(
            events_for_decision=lambda _decision_id, _event_type: [
                {
                    "event_id": "proof-conflict",
                    "source": "runtime_executor",
                    "event_type": event_type,
                    "decision_id": "decision-1",
                    "payload": payload,
                }
            ]
        )
    )
    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_VERIFIED_SOURCE_EVENT_REQUIRED",
    ):
        _source_proof_event(
            coordinator,
            decision_id="decision-1",
            proof_event_type=event_type,
            ok=True,
        )
