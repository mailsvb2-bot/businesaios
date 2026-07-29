from __future__ import annotations

from datetime import UTC, datetime, timedelta

from application.evidence.evidence_verifier import EvidenceVerifier
from execution.verification.evidence_types import EvidenceItem


def _item(*, observed_at: datetime) -> EvidenceItem:
    return EvidenceItem(
        source="connector",
        kind="connector_snapshot",
        status="verified",
        action_id="action-1",
        action_type="send_message@v1",
        external_refs=("provider-message-1",),
        confidence=1.0,
        payload={"ok": True},
        observed_at=observed_at,
    )


def test_evidence_identity_does_not_depend_on_observation_clock() -> None:
    first = _item(observed_at=datetime(2026, 7, 29, 10, 0, tzinfo=UTC))
    second = _item(observed_at=first.observed_at + timedelta(seconds=30))

    assert first.observed_at != second.observed_at
    assert first.evidence_id == second.evidence_id
    assert first.stable_identity() == second.stable_identity()


def test_verifier_replay_uses_signed_action_time_for_missing_evidence_time() -> None:
    action = {
        "action_id": "action-1",
        "action_type": "send_message@v1",
        "requested_at": "2026-07-29T10:00:00+00:00",
    }
    router = {
        "source": "connector",
        "verified": True,
        "status": "verified",
        "external_refs": ["provider-message-1"],
        "confidence": 1.0,
    }

    first = EvidenceVerifier().verify(action=action, router_evidence=router)
    second = EvidenceVerifier().verify(action=action, router_evidence=router)

    assert first.verification["decision_fingerprint"] == second.verification["decision_fingerprint"]
    assert first.verification["matched_evidence_ids"] == second.verification["matched_evidence_ids"]
    assert first.evidence_bundle == second.evidence_bundle
    assert first.verification["engine"]["evidence"] == second.verification["engine"]["evidence"]
    assert first.evidence_bundle["records"][0]["observed_at"] == action["requested_at"]
    assert first.verification["engine"]["evidence"][0]["observed_at"] == action["requested_at"]
