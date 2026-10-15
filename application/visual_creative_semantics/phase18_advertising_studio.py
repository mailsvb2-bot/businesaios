"""Phase-18 donor advertising studio: pure, approval-bound creative preparation.

No provider IO, scheduler, autonomous spending, or second campaign registry.
Only the existing DecisionCore/Execution path may dispatch an approved brief.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

CANON_PHASE18_AD_STUDIO_ADVISORY_ONLY = True
ANGLES = (
    ("human_trust", "Credible professional presence, natural light, no invented endorsements."),
    ("clear_process", "Show the next practical service step with uncluttered copy space."),
    ("calm_value", "Show everyday usefulness without guarantees or dramatic before/after."),
)
FORMATS = {"square": (1080, 1080), "feed": (1080, 1350),
           "story": (1080, 1920), "landscape": (1200, 628)}


def _required(value: str, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not (clean := " ".join(value.split())) or len(clean) > maximum:
        raise ValueError(f"advertising_{label}_invalid")
    return clean


@dataclass(frozen=True)
class AdvertisingCreativeBrief:
    tenant_id: str
    business_id: str
    campaign_id: str
    creative_id: str
    kind: str
    angle: str
    prompt: str
    headline: str
    description: str
    formats: tuple[str, ...]
    brand_fingerprint: str
    approval_fingerprint: str
    generation_status: str = "draft"
    publication_status: str = "not_authorized"
    spend_authorized: bool = False


def prepare_advertising_creatives(
    *, tenant_id: str, business_id: str, campaign_id: str, headline: str,
    description: str, brand_context: str, kind: str, formats: tuple[str, ...],
    campaign_goal: str, country_code: str = "",
) -> tuple[AdvertisingCreativeBrief, ...]:
    scope = {name: _required(value, name, limit) for name, value, limit in (
        ("tenant_id", tenant_id, 128), ("business_id", business_id, 128),
        ("campaign_id", campaign_id, 128), ("headline", headline, 160),
        ("description", description, 500), ("brand_context", brand_context, 4000),
        ("campaign_goal", campaign_goal, 280),
    )}
    if kind not in {"image", "video"}:
        raise ValueError("advertising_kind_invalid")
    if not isinstance(formats, (tuple, list)) or not formats or len(formats) > 4:
        raise ValueError("advertising_formats_invalid")
    normalized = tuple(dict.fromkeys(formats))
    if len(normalized) != len(formats) or any(f not in FORMATS for f in normalized):
        raise ValueError("advertising_formats_invalid")
    country = country_code.strip().upper()
    if country and (len(country) != 2 or not country.isalpha()):
        raise ValueError("advertising_country_invalid")
    brand_digest = hashlib.sha256(scope["brand_context"].encode()).hexdigest()
    rows = []
    for angle, direction in ANGLES:
        subject = {
            "tenant_id": scope["tenant_id"], "business_id": scope["business_id"],
            "campaign_id": scope["campaign_id"], "headline": scope["headline"],
            "description": scope["description"], "brand_fingerprint": brand_digest,
            "goal": scope["campaign_goal"], "kind": kind,
            "angle": angle, "formats": normalized, "country_code": country,
        }
        fingerprint = hashlib.sha256(json.dumps(
            subject, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        prompt = (
            f"Create a {kind} advertising asset. Goal: {scope['campaign_goal']}. "
            f"Service: {scope['headline']}. Context: {scope['description']}. "
            f"Visual direction: {direction} Brand context: {scope['brand_context']}. "
            "Avoid fake reviews, invented statistics, medical or income guarantees, "
            "misleading urgency, or before/after transformation claims. "
            "Leave copy space; typography is applied by the approved compositor."
        )
        rows.append(AdvertisingCreativeBrief(
            tenant_id=scope["tenant_id"], business_id=scope["business_id"],
            campaign_id=scope["campaign_id"], creative_id="ad_" + fingerprint[:24],
            kind=kind, angle=angle, prompt=prompt,
            headline=scope["headline"], description=scope["description"],
            formats=normalized, brand_fingerprint=brand_digest,
            approval_fingerprint=fingerprint,
        ))
    return tuple(rows)


def require_approved_visual_result(
    *, brief: AdvertisingCreativeBrief, approved_fingerprint: str,
    receipt: Mapping[str, object],
) -> Mapping[str, object]:
    """Verify the sealed media receipt without approving delivery or spending."""
    if approved_fingerprint != brief.approval_fingerprint:
        raise PermissionError("advertising_approval_changed")
    if not isinstance(receipt, Mapping) or (
        receipt.get("tenant_id") != brief.tenant_id
        or receipt.get("business_id") != brief.business_id
        or receipt.get("creative_id") != brief.creative_id
        or receipt.get("approval_fingerprint") != approved_fingerprint
        or receipt.get("kind") != brief.kind
        or receipt.get("status") != "succeeded"
    ):
        raise RuntimeError("advertising_media_receipt_unverified")
    sha = receipt.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise RuntimeError("advertising_media_hash_invalid")
    return {"creative_id": brief.creative_id, "sha256": sha, "kind": brief.kind,
            "verified_generation": True, "published": False, "spend_authorized": False}
