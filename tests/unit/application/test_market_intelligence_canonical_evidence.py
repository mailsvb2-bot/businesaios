from __future__ import annotations

from copy import deepcopy

import pytest

from application.evidence.market_intelligence_evidence import (
    persist_market_intelligence_derived_evidence,
    project_market_intelligence_derived_evidence,
)
from runtime.boot.market_intelligence_boot import build_market_intelligence_runtime
from storage.evidence_store import InMemoryEvidenceStore


def _derived(**overrides):
    payload = {
        "evidence_id": "market-derived-1",
        "tenant_id": "tenant-a",
        "business_id": "unknown",
        "derived_kind": "market_signal_summary",
        "policy_name": "market_intelligence_derived_evidence_v1",
        "confidence": 0.8,
        "raw_refs": [
            {
                "provider": "amazon",
                "source_family": "marketplace",
                "external_id": "sku-1",
                "observed_at": "2026-09-14T12:00:00+00:00",
                "checksum": "abc123",
            }
        ],
        "explainability": {"ranking_policy_name": "market_intelligence_memory_promotion_v2"},
        "payload": {"promoted_signals": [{"external_id": "sku-1"}]},
    }
    payload.update(overrides)
    return payload


def _persist(store, *, derived=None, business_id=None):
    payload = derived or _derived()
    if business_id is not None and derived is None:
        payload = _derived(business_id=business_id)
    return persist_market_intelligence_derived_evidence(
        evidence_store=store,
        tenant_id="tenant-a",
        business_id=business_id,
        provider="amazon",
        source_family="marketplace",
        derived_evidence=payload,
    )


def test_market_intelligence_derived_evidence_is_canonical_and_unknown_first() -> None:
    store = InMemoryEvidenceStore()
    record = _persist(store)
    assert record.evidence_id == "market-derived-1"
    assert record.business_id == "unknown"
    assert record.observed_at is None
    assert record.source == "amazon"
    assert record.source_type == "market_intelligence_derived"
    assert record.lineage == {
        "source": "marketplace:amazon",
        "normalization": "market-intelligence-derived:market-derived-1",
        "derived_fact": "market-derived-1",
    }
    assert record.refs == ("market-raw:amazon:marketplace:sku-1", "sha256:abc123")
    assert record.lineage_complete is False
    assert store.get(tenant_id="tenant-a", evidence_id="market-derived-1") == record


def test_market_intelligence_derived_evidence_replay_is_idempotent_and_conflict_fails_closed() -> None:
    store = InMemoryEvidenceStore()
    first = _persist(store, business_id="business-a")
    second = _persist(store, business_id="business-a")
    assert second == first
    assert store.list_for_tenant(tenant_id="tenant-a") == (first,)

    changed = deepcopy(_derived(business_id="business-a"))
    changed["payload"] = {"promoted_signals": [{"external_id": "sku-1", "price": 99}]}
    with pytest.raises(ValueError, match="replay conflicts with canonical evidence"):
        _persist(store, derived=changed, business_id="business-a")


def test_market_intelligence_derived_evidence_rejects_cross_tenant_binding() -> None:
    store = InMemoryEvidenceStore()
    with pytest.raises(ValueError, match="tenant mismatch"):
        _persist(store, derived=_derived(tenant_id="tenant-other"))
    assert store.list_for_tenant(tenant_id="tenant-a") == ()


def test_market_intelligence_projection_preserves_only_explicit_business_identity() -> None:
    record = project_market_intelligence_derived_evidence(
        tenant_id="tenant-a",
        business_id="business-a",
        provider="amazon",
        source_family="marketplace",
        derived_evidence=_derived(business_id="business-a"),
    )
    assert record.business_id == "business-a"
    assert record.labels["provider"] == "amazon"


def test_market_intelligence_runtime_composition_accepts_one_canonical_evidence_store() -> None:
    store = InMemoryEvidenceStore()
    runtime = build_market_intelligence_runtime(
        execute_action=lambda _action, _payload: {"ok": True, "executed": True, "records": []},
        evidence_store=store,
    )
    assert runtime.loop.evidence_store is store


def test_market_intelligence_derived_identity_is_business_scoped_and_checksum_bound() -> None:
    from execution.market_intelligence_derived_evidence_governance import (
        MarketIntelligenceDerivedEvidenceGovernance,
    )

    governance = MarketIntelligenceDerivedEvidenceGovernance()
    raw = [{"provider": "amazon", "source_family": "marketplace", "external_id": "sku-1", "price": 10}]
    kwargs = {
        "tenant_id": "tenant-a",
        "derived_kind": "market_signal_summary",
        "confidence": 0.8,
        "raw_records": raw,
        "payload": {"promoted_signals": [{"external_id": "sku-1"}]},
        "ranking_policy_name": "market_intelligence_memory_promotion_v2",
        "explainability": {"promoted_count": 1},
    }
    first = governance.build(business_id="business-a", **kwargs)
    replay = governance.build(business_id="business-a", **kwargs)
    other_business = governance.build(business_id="business-b", **kwargs)
    changed_raw = governance.build(
        business_id="business-a",
        **{**kwargs, "raw_records": [{**raw[0], "price": 11}]},
    )
    assert replay.evidence_id == first.evidence_id
    assert other_business.evidence_id != first.evidence_id
    assert changed_raw.evidence_id != first.evidence_id
    assert first.business_id == "business-a"
