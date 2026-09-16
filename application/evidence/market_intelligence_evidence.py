from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_MARKET_INTELLIGENCE_EVIDENCE_PROJECTION = True


def _text(value: object) -> str:
    return str(value or "").strip()


def _confidence(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("market intelligence derived evidence confidence is required") from exc
    if not 0.0 <= number <= 1.0:
        raise ValueError("market intelligence derived evidence confidence must be between 0 and 1")
    return number


def _raw_refs(payload: Mapping[str, Any]) -> tuple[str, ...]:
    raw_refs = payload.get("raw_refs")
    if not isinstance(raw_refs, list | tuple):
        raise ValueError("market intelligence derived evidence raw_refs must be a sequence")
    refs: list[str] = []
    for raw in raw_refs:
        if not isinstance(raw, Mapping):
            raise ValueError("market intelligence derived evidence raw_refs must contain objects")
        provider = _text(raw.get("provider"))
        source_family = _text(raw.get("source_family"))
        external_id = _text(raw.get("external_id"))
        checksum = _text(raw.get("checksum"))
        if external_id:
            refs.append(f"market-raw:{provider or 'unknown'}:{source_family or 'unknown'}:{external_id}")
        if checksum:
            refs.append(f"sha256:{checksum}")
    return tuple(dict.fromkeys(refs))


def project_market_intelligence_derived_evidence(
    *,
    tenant_id: str,
    business_id: str | None,
    provider: str,
    source_family: str,
    derived_evidence: Mapping[str, Any],
    created_at: datetime | None = None,
) -> EvidenceRecord:
    payload = dict(derived_evidence or {})
    evidence_id = _text(payload.get("evidence_id"))
    derived_tenant_id = _text(payload.get("tenant_id"))
    normalized_tenant_id = _text(tenant_id)
    normalized_provider = _text(provider)
    normalized_source_family = _text(source_family)
    derived_kind = _text(payload.get("derived_kind"))
    policy_name = _text(payload.get("policy_name"))
    if not evidence_id:
        raise ValueError("market intelligence derived evidence_id is required")
    if not normalized_tenant_id:
        raise ValueError("market intelligence tenant_id is required")
    if derived_tenant_id and derived_tenant_id != normalized_tenant_id:
        raise ValueError("market intelligence derived evidence tenant mismatch")
    if not normalized_provider or not normalized_source_family:
        raise ValueError("market intelligence provider and source_family are required")
    normalized_business_id = _text(business_id) or "unknown"
    derived_business_id = _text(payload.get("business_id"))
    if derived_business_id and derived_business_id != normalized_business_id:
        raise ValueError("market intelligence derived evidence business mismatch")
    if not derived_kind or not policy_name:
        raise ValueError("market intelligence derived_kind and policy_name are required")
    if not isinstance(payload.get("payload"), Mapping):
        raise ValueError("market intelligence derived evidence payload must be an object")
    if not isinstance(payload.get("explainability"), Mapping):
        raise ValueError("market intelligence derived evidence explainability must be an object")

    kwargs: dict[str, Any] = {}
    if created_at is not None:
        kwargs["created_at"] = created_at
    return EvidenceRecord(
        evidence_id=evidence_id,
        tenant_id=normalized_tenant_id,
        scope="market_intelligence",
        run_id=f"market-intelligence:{evidence_id}",
        action_type="market_intelligence_derived_evidence",
        verification_status="recorded",
        source=normalized_provider,
        source_type="market_intelligence_derived",
        business_id=normalized_business_id,
        observed_at=None,
        confidence=_confidence(payload.get("confidence")),
        privacy_class="internal",
        retention_policy="market_intelligence_evidence",
        lineage={
            "source": f"{normalized_source_family}:{normalized_provider}",
            "normalization": f"market-intelligence-derived:{evidence_id}",
            "derived_fact": evidence_id,
        },
        refs=_raw_refs(payload),
        payload=payload,
        labels={
            "provider": normalized_provider,
            "source_family": normalized_source_family,
            "derived_kind": derived_kind,
            "policy_name": policy_name,
        },
        **kwargs,
    ).normalized_for_write()


def persist_market_intelligence_derived_evidence(
    *,
    evidence_store: EvidenceStore,
    tenant_id: str,
    business_id: str | None,
    provider: str,
    source_family: str,
    derived_evidence: Mapping[str, Any],
) -> EvidenceRecord:
    evidence_id = _text(derived_evidence.get("evidence_id"))
    existing = evidence_store.get(tenant_id=tenant_id, evidence_id=evidence_id) if evidence_id else None
    expected = project_market_intelligence_derived_evidence(
        tenant_id=tenant_id,
        business_id=business_id,
        provider=provider,
        source_family=source_family,
        derived_evidence=derived_evidence,
        created_at=None if existing is None else existing.created_at,
    )
    if existing is not None:
        if existing != expected:
            raise ValueError("market intelligence derived evidence replay conflicts with canonical evidence")
        return existing
    try:
        return evidence_store.append(expected)
    except ValueError as exc:
        current = evidence_store.get(tenant_id=tenant_id, evidence_id=expected.evidence_id)
        if current is not None:
            replay = project_market_intelligence_derived_evidence(
                tenant_id=tenant_id,
                business_id=business_id,
                provider=provider,
                source_family=source_family,
                derived_evidence=derived_evidence,
                created_at=current.created_at,
            )
            if current == replay:
                return current
        raise ValueError("market intelligence derived evidence replay conflicts with canonical evidence") from exc


__all__ = [
    "CANON_MARKET_INTELLIGENCE_EVIDENCE_PROJECTION",
    "persist_market_intelligence_derived_evidence",
    "project_market_intelligence_derived_evidence",
]
