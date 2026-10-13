"""Bounded support diagnostic permission from canonical case facts, no second ACL."""
from __future__ import annotations

import pytest

from application.business_autonomy.support_case_registry import SupportCaseRegistry
from application.business_autonomy.support_case_access import SupportCaseDiagnosticAccess
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def prepared():
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    cases = SupportCaseRegistry(event_store=events, idempotency_store=claims)
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    item = cases.create(
        **scope, actor_id="owner-a", category="technical",
        summary="Message delivery not confirmed", idempotency_key="create",
    )
    item = cases.transition(
        **scope, case_id=item["id"], operator_id="operator-a",
        action="claim", expected_revision=1, idempotency_key="claim",
    )
    access = SupportCaseDiagnosticAccess(support_cases=cases)
    return events, claims, cases, access, scope, item


def test_consent_lifecycle_replay_expiry_and_bounded_audit_survive_restart():
    events, claims, cases, access, scope, item = prepared()
    kw = {**scope, "case_id": item["id"]}
    assert access.state(**kw, now_ms=1000)["reason"] == "not_granted"
    with pytest.raises(RuntimeError, match="no_live_consent"):
        access.diagnostics(**kw, operator_id="operator-a",
                           idempotency_key="before-consent", now_ms=1000)
    granted = access.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                           duration_seconds=300, idempotency_key="grant", now_ms=1000)
    assert granted["active"] is True and granted["expires_at_ms"] == 301000
    assert access.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                        duration_seconds=300, idempotency_key="grant", now_ms=2000)["grant_id"] == granted["grant_id"]
    with pytest.raises(RuntimeError, match="existing_grant_active"):
        access.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                     duration_seconds=300, idempotency_key="second-grant", now_ms=2000)
    receipt = access.diagnostics(**kw, operator_id="operator-a",
                                 idempotency_key="view-one", now_ms=3000)
    assert set(receipt["counts"]) == {"messages", "payments", "programs", "support"}
    assert receipt["counts"]["support"] >= 2
    assert access.diagnostics(**kw, operator_id="operator-a",
                              idempotency_key="view-one", now_ms=4000) == receipt
    assert access.state(**kw, now_ms=4000)["views"] == 1
    assert [row["action"] for row in access.audit(**kw)["entries"]] == [
        "granted", "diagnostics_viewed",
    ]
    assert len(events) == 4  # case created/claimed, grant, one diagnostic disclosure
    # Same source of truth from fresh readers, no local persisted session.
    restarted = SupportCaseDiagnosticAccess(support_cases=SupportCaseRegistry(
        event_store=events, idempotency_store=claims,
    ))
    assert restarted.state(**kw, now_ms=301000)["reason"] == "expired"
    with pytest.raises(RuntimeError, match="no_live_consent"):
        restarted.diagnostics(**kw, operator_id="operator-a",
                              idempotency_key="expired", now_ms=301000)
    assert restarted.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                           duration_seconds=60, idempotency_key="new-after-expiry",
                           now_ms=302000)["active"]
    assert restarted.state(**kw, now_ms=302500)["views"] == 0
    latest = restarted.state(**kw, now_ms=302500)
    revoked = restarted.revoke(**kw, owner_id="owner-a", grant_id=latest["grant_id"],
                               idempotency_key="revoke", now_ms=302600)
    assert revoked["reason"] == "revoked"
    assert restarted.revoke(**kw, owner_id="owner-a", grant_id=latest["grant_id"],
                            idempotency_key="revoke", now_ms=302700) == revoked
    with pytest.raises(RuntimeError, match="no_live_consent"):
        restarted.diagnostics(**kw, operator_id="operator-a",
                              idempotency_key="after-revoke", now_ms=302800)


def test_case_transitions_wrong_operator_and_scope_immediately_block_disclosure():
    events, claims, cases, access, scope, case = prepared()
    kw = {**scope, "case_id": case["id"]}
    assert access.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                        duration_seconds=300, idempotency_key="grant", now_ms=1000)["active"]
    with pytest.raises(RuntimeError, match="no_live_consent"):
        access.diagnostics(**kw, operator_id="another-operator", idempotency_key="stolen",
                           now_ms=2000)
    with pytest.raises(KeyError):
        access.state(tenant_id="tenant-a", business_id="business-b",
                     case_id=case["id"], now_ms=2000)
    assert access.audit(**kw)["total"] == 1
    released = cases.transition(**scope, case_id=case["id"],
        operator_id="operator-a", action="release", expected_revision=2,
        idempotency_key="release")
    assert released["status"] == "open"
    assert access.state(**kw, now_ms=2000)["reason"] == "case_changed"
    with pytest.raises(RuntimeError, match="no_live_consent"):
        access.diagnostics(**kw, operator_id="operator-a", idempotency_key="stale",
                           now_ms=2000)
    re_claimed = cases.transition(**scope, case_id=case["id"],
        operator_id="operator-a", action="claim", expected_revision=3,
        idempotency_key="claim-again")
    assert re_claimed["revision"] == 4
    assert access.state(**kw, now_ms=2000)["reason"] == "case_changed"
    assert len(events) == 5


def test_no_unbounded_ttl_stale_revision_or_forged_grant_replay():
    _, _, _, access, scope, item = prepared()
    kw = {**scope, "case_id": item["id"]}
    for duration in (0, 59, 3601, True, "300"):
        with pytest.raises(ValueError, match="duration"):
            access.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                         duration_seconds=duration, idempotency_key="invalid", now_ms=1000)
    with pytest.raises(RuntimeError, match="case_not_claimed_or_stale"):
        access.grant(**kw, owner_id="owner-a", expected_case_revision=1,
                     duration_seconds=300, idempotency_key="stale", now_ms=1000)
    granted = access.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                           duration_seconds=300, idempotency_key="grant", now_ms=1000)
    with pytest.raises(RuntimeError, match="idempotency_conflict"):
        access.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                     duration_seconds=600, idempotency_key="grant", now_ms=1000)
    with pytest.raises(RuntimeError, match="grant_not_active"):
        access.revoke(**kw, owner_id="owner-a", grant_id="forged",
                      idempotency_key="revoke", now_ms=1001)
    assert access.state(**kw, now_ms=1001)["grant_id"] == granted["grant_id"]


def test_revoke_wins_concurrent_diagnostic_transition_guard(monkeypatch):
    _, _, _, access, scope, case = prepared()
    kw = {**scope, "case_id": case["id"]}
    active = access.grant(**kw, owner_id="owner-a", expected_case_revision=2,
                          duration_seconds=300, idempotency_key="grant", now_ms=1000)
    original = access._writer.append_transition_once

    def race(**payload):
        if payload["operation"] == "view_diagnostics":
            access.revoke(**kw, owner_id="owner-a", grant_id=active["grant_id"],
                          idempotency_key="owner-race", now_ms=1200)
        return original(**payload)

    monkeypatch.setattr(access._writer, "append_transition_once", race)
    with pytest.raises(RuntimeError, match="support_access_revision_conflict"):
        access.diagnostics(**kw, operator_id="operator-a",
                           idempotency_key="racing", now_ms=1100)
    assert access.audit(**kw)["total"] == 2  # grant and revoke, no disclosed count
