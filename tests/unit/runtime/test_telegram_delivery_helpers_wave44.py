from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import runtime._internal.effects_clients._telegram_delivery_state as state_sut
import runtime._internal.effects_clients._telegram_delivery_support as support_sut
from runtime.platform.delivery_state import ACCEPTED_PHASE, FINALIZED_PHASE, RECOVERY_PHASE


def test_stable_identity_and_metadata_contracts():
    left = {"b": 2, "a": "тест"}
    right = {"a": "тест", "b": 2}
    assert support_sut.stable_json(left) == support_sut.stable_json(right)
    assert support_sut.payload_digest(left) == support_sut.payload_digest(right)
    assert support_sut.delivery_key(method="send", chat_id="1", payload=left) == support_sut.delivery_key(
        method="send", chat_id="1", payload=right
    )
    assert support_sut.delivery_key(method="send", chat_id="2", payload=left) != support_sut.delivery_key(
        method="send", chat_id="1", payload=left
    )

    metadata = support_sut.build_delivery_metadata(
        method="send",
        chat_id=None,
        payload={"x": 1},
        timeout_s=0,
        priority="high",
        critical=1,
        mode="queued",
        delivery_key="key",
        payload_digest="digest",
        extra={"delivery_phase": ACCEPTED_PHASE},
    )
    assert metadata["chat_id"] is None
    assert metadata["timeout_s"] == 0
    assert metadata["critical"] is True
    assert metadata["delivery_phase"] == ACCEPTED_PHASE
    assert support_sut.build_delivery_metadata(
        method="send",
        chat_id=7,
        payload={},
        timeout_s=2,
        priority=None,
        critical=False,
        mode="direct",
        delivery_key="key",
        payload_digest="digest",
    )["chat_id"] == "7"


def test_phase_projection_all_sources():
    assert support_sut.phase_from_receipt(None, default="fallback") == "fallback"
    assert support_sut.phase_from_receipt({"delivery_phase": "direct"}) == "direct"
    assert support_sut.phase_from_receipt(
        {"metadata": {"delivery_phase": RECOVERY_PHASE}}
    ) == RECOVERY_PHASE
    assert support_sut.phase_from_receipt({"metadata": "bad"}, default="fallback") == "fallback"


def test_accepted_receipt_staleness_all_branches(monkeypatch):
    now_ms = 1_000_000
    monkeypatch.setattr(support_sut.time, "time", lambda: now_ms / 1000)
    assert support_sut.accepted_receipt_is_stale(None) is False
    assert support_sut.accepted_receipt_is_stale({"delivery_phase": FINALIZED_PHASE}) is False
    assert support_sut.accepted_receipt_is_stale(
        {"delivery_phase": ACCEPTED_PHASE, "accepted_at_ms": "bad"}
    ) is False
    assert support_sut.accepted_receipt_is_stale(
        {"delivery_phase": ACCEPTED_PHASE, "accepted_at_ms": 0}
    ) is False
    recent = {
        "delivery_phase": ACCEPTED_PHASE,
        "accepted_at_ms": now_ms - 10_000,
        "metadata": {"timeout_s": 1},
    }
    assert support_sut.accepted_receipt_is_stale(recent) is False
    stale = {
        "metadata": {"delivery_phase": RECOVERY_PHASE, "timeout_s": 20},
        "delivered_at_ms": now_ms - 50_000,
    }
    assert support_sut.accepted_receipt_is_stale(stale) is True


def test_existing_receipt_paths():
    assert state_sut.existing_receipt(None, delivery_key="key") is None
    assert state_sut.existing_receipt(object(), delivery_key="key") is None
    failing = SimpleNamespace(get_receipt=Mock(side_effect=RuntimeError("boom")))
    assert state_sut.existing_receipt(failing, delivery_key="key") is None
    mapping = SimpleNamespace(get_receipt=Mock(return_value={"phase": "accepted"}))
    assert state_sut.existing_receipt(mapping, delivery_key="key") == {"phase": "accepted"}
    nonmapping = SimpleNamespace(get_receipt=Mock(return_value="bad"))
    assert state_sut.existing_receipt(nonmapping, delivery_key="key") is None


def test_state_delegates_phase_and_metadata(monkeypatch):
    phase = Mock(return_value="phase")
    build = Mock(return_value={"meta": True})
    monkeypatch.setattr(state_sut, "phase_from_receipt", phase)
    monkeypatch.setattr(state_sut, "build_delivery_metadata", build)
    assert state_sut.receipt_phase({"a": 1}, default="d") == "phase"
    phase.assert_called_once_with({"a": 1}, default="d")
    assert state_sut.delivery_metadata(
        method="send",
        chat_id="1",
        payload={},
        timeout_s=1,
        priority="p",
        critical=False,
        mode="m",
        delivery_key="key",
        payload_digest="digest",
        extra={"x": 1},
    ) == {"meta": True}
    assert build.call_args.kwargs["extra"] == {"x": 1}


def test_mark_accepted_and_delivered_are_best_effort():
    state_sut.mark_transport_accepted(None, delivery_key="key", payload_digest="digest", metadata={})
    accepted = SimpleNamespace(mark_accepted=Mock())
    state_sut.mark_transport_accepted(
        accepted, delivery_key="key", payload_digest="digest", metadata={"x": 1}
    )
    assert accepted.mark_accepted.call_args.args == ("key",)
    accepted.mark_accepted.side_effect = RuntimeError("boom")
    state_sut.mark_transport_accepted(
        accepted, delivery_key="key", payload_digest="digest", metadata={}
    )

    state_sut.mark_transport_delivered(
        None,
        delivery_key="key",
        external_id=None,
        payload_digest="digest",
        metadata={},
    )
    delivered = SimpleNamespace(mark_delivered=Mock())
    state_sut.mark_transport_delivered(
        delivered,
        delivery_key="key",
        external_id=None,
        payload_digest="digest",
        metadata={},
    )
    assert delivered.mark_delivered.call_args.kwargs["external_id"] is None
    state_sut.mark_transport_delivered(
        delivered,
        delivery_key="key",
        external_id=9,
        payload_digest="digest",
        metadata={"x": 1},
    )
    assert delivered.mark_delivered.call_args.kwargs["external_id"] == "9"
    delivered.mark_delivered.side_effect = RuntimeError("boom")
    state_sut.mark_transport_delivered(
        delivered,
        delivery_key="key",
        external_id="9",
        payload_digest="digest",
        metadata={},
    )


def test_recover_stale_receipt_paths():
    assert state_sut.recover_stale_receipt(
        None, delivery_key="key", payload_digest="digest", metadata={}
    ) is None
    failing = SimpleNamespace(mark_recovery_queued=Mock(side_effect=RuntimeError("boom")))
    assert state_sut.recover_stale_receipt(
        failing, delivery_key="key", payload_digest="digest", metadata={}
    ) is None
    mapping = SimpleNamespace(mark_recovery_queued=Mock(return_value={"phase": "recovery"}))
    assert state_sut.recover_stale_receipt(
        mapping, delivery_key="key", payload_digest="digest", metadata={}
    ) == {"phase": "recovery"}
    nonmapping = SimpleNamespace(mark_recovery_queued=Mock(return_value="bad"))
    assert state_sut.recover_stale_receipt(
        nonmapping, delivery_key="key", payload_digest="digest", metadata={}
    ) is None


def test_recover_inflight_receipts_filters_and_projects(monkeypatch):
    assert state_sut.recover_inflight_accepted_receipts(
        None, stale_after_ms=10, limit=2
    ) == []
    failing = SimpleNamespace(
        list_stale_accepted_receipts=Mock(side_effect=RuntimeError("boom"))
    )
    assert state_sut.recover_inflight_accepted_receipts(
        failing, stale_after_ms=10, limit=2
    ) == []

    source = SimpleNamespace(
        list_stale_accepted_receipts=Mock(
            return_value=[
                "bad",
                {
                    "message_id": "m1",
                    "payload_digest": "d1",
                    "metadata": {"payload_digest": "fallback"},
                },
                {"message_id": "m2", "metadata": "bad"},
            ]
        )
    )
    recover = Mock(side_effect=[{"message_id": "m1"}, None])
    monkeypatch.setattr(state_sut, "recover_stale_receipt", recover)
    assert state_sut.recover_inflight_accepted_receipts(
        source, stale_after_ms=10, limit=2
    ) == [{"message_id": "m1"}]
    source.list_stale_accepted_receipts.assert_called_once_with(
        older_than_ms=10, limit=2
    )
    assert recover.call_args_list[0].kwargs["metadata"]["delivery_phase"] == RECOVERY_PHASE
    assert recover.call_args_list[1].kwargs["payload_digest"] == ""

    source.list_stale_accepted_receipts.return_value = None
    assert state_sut.recover_inflight_accepted_receipts(
        source, stale_after_ms=10, limit=2
    ) == []


def test_accepted_stale_delegate(monkeypatch):
    delegated = Mock(return_value=True)
    monkeypatch.setattr(state_sut, "accepted_receipt_is_stale", delegated)
    receipt = {"phase": "accepted"}
    assert state_sut.accepted_receipt_stale(receipt) is True
    delegated.assert_called_once_with(receipt)
