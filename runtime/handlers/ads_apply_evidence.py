from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANON_ADS_APPLY_EVIDENCE_BRIDGE = True

_ID_KEYS = frozenset({"id", "external_id", "campaign_id", "ad_id", "adset_id", "group_id", "request_id"})


def _provider_refs(value: object) -> list[str]:
    refs: list[str] = []

    def _walk(item: object) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if str(key).strip().casefold() in _ID_KEYS:
                    text = str(child or "").strip()
                    if text and text not in refs:
                        refs.append(text)
                _walk(child)
        elif isinstance(item, list | tuple):
            for child in item:
                _walk(child)

    _walk(value)
    return refs


def build_ads_apply_evidence(*, status: str, detail: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized_status = str(status or "").strip().casefold()
    detail_map = dict(detail or {})
    provider = detail_map.get("provider") if isinstance(detail_map.get("provider"), Mapping) else None
    applied = normalized_status == "applied"
    provider_observed = applied and provider is not None and bool(provider)

    return {
        "source": "connector" if applied else "runtime_execution_contract",
        "action_type": "ads.apply",
        "verified": provider_observed,
        "status": "verified" if provider_observed else ("failed" if applied else "observed"),
        "summary": "ads_provider_apply_observed" if provider_observed else f"ads_apply_{normalized_status or 'unknown'}",
        "external_refs": _provider_refs(provider or {}),
        "confidence": 1.0 if provider_observed else 0.0,
        "payload": {
            "ads_apply_status": normalized_status or "unknown",
            "provider_observed": provider_observed,
        },
    }


def attach_ads_apply_outcome(*, notification: object, status: str, detail: Mapping[str, Any] | None) -> dict[str, Any]:
    result = dict(notification) if isinstance(notification, Mapping) else {"ok": bool(notification)}
    result["ads_apply_status"] = str(status or "unknown")
    result["ads_apply_detail"] = dict(detail or {})
    result["evidence"] = build_ads_apply_evidence(status=status, detail=detail)
    return result


__all__ = [
    "CANON_ADS_APPLY_EVIDENCE_BRIDGE",
    "attach_ads_apply_outcome",
    "build_ads_apply_evidence",
]
