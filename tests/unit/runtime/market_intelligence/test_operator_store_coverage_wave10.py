from __future__ import annotations

import json

import pytest

from execution.market_intelligence_operator_store import (
    PersistentMarketIntelligenceOperatorStore,
    ReviewQueueRecord,
    _positive_int,
    _review_status,
    _store_path,
    _text,
)


def record(review_id: str = "review:1", **overrides) -> ReviewQueueRecord:
    payload = {
        "review_id": review_id,
        "tenant_id": " tenant-a ",
        "provider": " provider-a ",
        "source_family": " search ",
        "external_id": " ",
        "reason": " reason ",
        "payload": {"x": 1},
    }
    payload.update(overrides)
    return ReviewQueueRecord(**payload)


def test_helpers_and_default_paths(monkeypatch, tmp_path):
    assert _text(None, default="x") == "x"
    assert _text(" value ") == "value"
    assert _positive_int("bad") == 1
    assert _positive_int(0, default=7) == 7
    assert _positive_int("4") == 4
    assert _review_status("") == "open"
    with pytest.raises(ValueError, match="unsupported review status"):
        _review_status("future")

    monkeypatch.setenv("BUSINESAIOS_MARKET_INTELLIGENCE_OPERATOR_STORE_PATH", str(tmp_path / "explicit.json"))
    assert _store_path() == tmp_path / "explicit.json"
    monkeypatch.delenv("BUSINESAIOS_MARKET_INTELLIGENCE_OPERATOR_STORE_PATH")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    assert _store_path() == tmp_path / "data" / "governance" / "market_intelligence_operator_store.json"


def test_record_normalization_validation_and_dict_shape():
    item = record()
    assert item.tenant_id == "tenant-a"
    assert item.provider == "provider-a"
    assert item.source_family == "search"
    assert item.external_id == "unknown"
    assert item.reason == "reason"
    assert item.status == "open"
    assert item.created_at
    assert item.resolved_at is None
    assert item.resolution is None
    assert item.operator_id is None
    assert item.as_dict()["payload"] == {"x": 1}

    with pytest.raises(ValueError, match="review_id is required"):
        record(" ")
    with pytest.raises(ValueError, match="unsupported review status"):
        record(status="future")


def test_store_allocate_put_get_list_transition_and_reload(tmp_path):
    path = tmp_path / "operator.json"
    store = PersistentMarketIntelligenceOperatorStore(path)
    assert store.get_review("missing") is None
    assert store.transition_review(review_id="missing", status="open") is None

    first_id = store.allocate_review_id()
    first = record(first_id, created_at="2026-01-02T00:00:00+00:00")
    assert store.put_review(first) is first
    assert store.put_review(first) == first
    with pytest.raises(ValueError, match="review_id collision"):
        store.put_review(record(first_id, tenant_id="tenant-b"))

    second_id = store.allocate_review_id()
    second = record(second_id, tenant_id="tenant-b", created_at="2026-01-01T00:00:00+00:00")
    store.put_review(second)
    assert [item.review_id for item in store.list_reviews()] == [second_id, first_id]
    assert store.list_reviews(tenant_id="tenant-a") == (first,)
    assert store.list_reviews(tenant_id="") == ()

    claimed = store.transition_review(review_id=first_id, status="in_review", operator_id=" op ")
    assert claimed is not None and claimed.status == "in_review" and claimed.operator_id == "op"
    assert store.list_reviews(open_only=True) == (second,)
    with pytest.raises(ValueError, match="requires a resolution"):
        store.transition_review(review_id=first_id, status="resolved")
    resolved = store.resolve_review(review_id=first_id, resolution=" false_positive ", operator_id=" op ")
    assert resolved is not None and resolved.resolved_at and resolved.resolution == "false_positive"
    resolved_again = store.resolve_review(review_id=first_id, resolution="false_positive", operator_id="op")
    assert resolved_again is not None and resolved_again.resolved_at == resolved.resolved_at
    with pytest.raises(ValueError, match="resolved review cannot transition"):
        store.transition_review(review_id=first_id, status="open")

    reloaded = PersistentMarketIntelligenceOperatorStore(path)
    assert reloaded.get_review(first_id) == resolved
    assert reloaded.allocate_review_id() == "review:3"


def test_allocation_skips_existing_ids_and_handles_corrupt_entries(tmp_path):
    store = PersistentMarketIntelligenceOperatorStore(tmp_path / "operator.json")
    store._state["next_review_seq"] = "bad"
    store._state["reviews"] = {"review:1": record().as_dict()}
    assert store.allocate_review_id() == "review:2"

    store._state["reviews"]["broken"] = "not-a-record"
    assert store.get_review("broken") is None
    assert [item.review_id for item in store.list_reviews()] == ["review:1"]
    with pytest.raises(ValueError, match="corrupt review record"):
        store.put_review(record("broken"))


def test_audit_ban_allow_snapshot_and_trim(tmp_path, monkeypatch):
    store = PersistentMarketIntelligenceOperatorStore(tmp_path / "operator.json")
    monkeypatch.setattr(store, "_flush", lambda: None)
    store.add_audit(action="first", payload={})
    store._state["audit_log"] = [
        {"at": str(index), "action": "old", "payload": {}}
        for index in range(2000)
    ]
    store.add_audit(action=" new ", payload={"x": 1})
    store._state["audit_log"].append("broken")
    audit = store.audit_log()
    assert len(audit) == 2000
    assert audit[-1]["action"] == "new"

    store.add_ban(tenant_id="", provider=" p ", scope_key=" s ")
    store.add_ban(tenant_id="", provider=" p ", scope_key=" s ")
    assert store.is_banned(tenant_id="default", provider="p", scope_key="s")
    store.add_allow(tenant_id="default", provider="p", scope_key="s")
    store.add_allow(tenant_id="default", provider="p", scope_key="s")
    assert not store.is_banned(tenant_id="default", provider="p", scope_key="s")
    snapshot = store.snapshot()
    assert snapshot["banlist"] == [("default", "p", "s")]
    assert snapshot["allowlist"] == [("default", "p", "s")]
    assert len(snapshot["audit_log"]) == 2000


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "root must be a mapping"),
        ({"reviews": []}, "reviews must be a mapping"),
        ({"reviews": {}, "audit_log": {}}, "audit_log must be a list"),
        ({"reviews": {}, "audit_log": [], "banlist": {}}, "source lists must be lists"),
        ({"reviews": {"review:1": "bad"}}, "review must be a mapping"),
        ({"reviews": {"other": record().as_dict()}}, "review key mismatch"),
    ],
)
def test_load_fails_closed_on_structural_corruption(tmp_path, payload, message):
    path = tmp_path / "operator.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        PersistentMarketIntelligenceOperatorStore(path)


def test_load_normalizes_sections_and_sequence(tmp_path):
    path = tmp_path / "operator.json"
    item = record()
    path.write_text(
        json.dumps(
            {
                "reviews": {item.review_id: item.as_dict()},
                "audit_log": [{"x": 1}, "bad"],
                "banlist": [["t", "p", "s"], "bad"],
                "allowlist": [("t", "p", "s")],
                "next_review_seq": -9,
            }
        ),
        encoding="utf-8",
    )
    store = PersistentMarketIntelligenceOperatorStore(path)
    assert store.audit_log() == ({"x": 1},)
    assert store.allocate_review_id() == "review:2"
    assert store.snapshot()["banlist"] == [("t", "p", "s")]
