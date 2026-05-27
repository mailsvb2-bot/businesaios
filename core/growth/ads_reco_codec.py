from __future__ import annotations

from typing import Any, Dict

from core.growth.recommendations import AdsObjectRef, AdsRecommendation


def reco_from_payload(p: Dict[str, Any]) -> AdsRecommendation:
    t = p.get("target") or {}
    target = AdsObjectRef(
        platform=str(t.get("platform") or "other"),
        account_id=str(t.get("account_id") or ""),
        object_type=str(t.get("object_type") or "campaign"),
        object_id=str(t.get("object_id") or ""),
    )
    return AdsRecommendation(
        rec_id=str(p.get("rec_id") or ""),
        title=str(p.get("title") or ""),
        rationale=str(p.get("rationale") or ""),
        target=target,
        patch=dict(p.get("patch") or {}),
        expected_impact=dict(p.get("expected_impact") or {}),
        risk_notes=p.get("risk_notes"),
    )
