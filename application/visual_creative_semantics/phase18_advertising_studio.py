"""Phase-18 donor advertising studio: pure, approval-bound creative preparation.

No provider IO, scheduler, autonomous spending, or second campaign registry.
Only the existing DecisionCore/Execution path may dispatch an approved brief.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from core.growth.ads.creative.prompting import parse_scene_json, render_pack_idempotency_key, scene_from_text

CANON_PHASE18_AD_STUDIO_ADVISORY_ONLY = True
ANGLES = (
    ("human_trust", "живой специалист в работе, естественный свет, спокойная достоверная атмосфера"),
    ("clear_process", "крупно ключевой шаг услуги, чистый фон, свободное место под текст"),
    ("calm_value", "результат в повседневной жизни клиента, мягкий свет, аккуратная композиция"),
)
AD_NEGATIVE_PROMPT = "выдуманные отзывы, цифры, цены, медицинские обещания, ложная срочность, надписи, логотипы, водяной знак"
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
    brand_context: str
    approval_fingerprint: str
    visual_direction: tuple[tuple[str, str], ...] = ()
    generation_status: str = "draft"
    publication_status: str = "not_authorized"
    spend_authorized: bool = False


def prepare_advertising_creatives(
    *, tenant_id: str, business_id: str, campaign_id: str, headline: str,
    description: str, brand_context: str, kind: str, formats: tuple[str, ...],
    campaign_goal: str, country_code: str = "", scene: Mapping[str, str] | None = None,
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
        shot = parse_scene_json(dict(scene or {})) or scene_from_text(f"{scope['headline']}. {scope['description']}")
        shot["style"] = direction
        subject = {
            "tenant_id": scope["tenant_id"], "business_id": scope["business_id"],
            "campaign_id": scope["campaign_id"], "headline": scope["headline"],
            "description": scope["description"], "brand_fingerprint": brand_digest,
            "goal": scope["campaign_goal"], "kind": kind,
            "angle": angle, "formats": normalized, "country_code": country, "scene": shot,
        }
        fingerprint = hashlib.sha256(json.dumps(
            subject, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        prompt = f"Рекламный {'видеоролик' if kind == 'video' else 'кадр'}: {shot.get('action') or shot['subject']}. {direction}."
        rows.append(AdvertisingCreativeBrief(
            tenant_id=scope["tenant_id"], business_id=scope["business_id"],
            campaign_id=scope["campaign_id"], creative_id="ad_" + fingerprint[:24],
            kind=kind, angle=angle, prompt=prompt,
            headline=scope["headline"], description=scope["description"],
            formats=normalized, brand_fingerprint=brand_digest,
            brand_context=scope["brand_context"], approval_fingerprint=fingerprint,
            visual_direction=tuple(shot.items()),
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


def build_approved_generation_action(
    *, brief: AdvertisingCreativeBrief, approval_reference: str,
    verify_approval, user_id: str, country_code: str = "",
) -> dict[str, object]:
    """Prepare existing visual_creative_generate@v1 ActionIntent payload only.

    Caller must submit through the canonical DecisionCore/Execution path.
    This function cannot invoke providers, make approvals, or start spending.
    """
    score, issues = preflight(brief.headline, brief.description)
    if score < 70 or "risky_claim" in issues:
        raise ValueError("unsafe_advertising_creative_variant")
    if not callable(verify_approval) or not isinstance(approval_reference, str) or not approval_reference.strip():
        raise PermissionError("advertising_approval_authority_required")
    if verify_approval(
        tenant_id=brief.tenant_id, business_id=brief.business_id,
        campaign_id=brief.campaign_id, creative_id=brief.creative_id,
        fingerprint=brief.approval_fingerprint, approval_reference=approval_reference,
    ) is not True:
        raise PermissionError("advertising_owner_approval_denied")
    actor = _required(user_id, "user_id", 128)
    return {
        "action_type": "visual_creative_generate@v1",
        "payload": {
            "tenant_id": brief.tenant_id, "user_id": actor,
            "kind": brief.kind, "prompt": brief.prompt,
            "brand_context": brief.brand_context, "negative_prompt": AD_NEGATIVE_PROMPT,
            "visual_direction": dict(brief.visual_direction),
            "country_code": country_code, "aspect_ratio": "9:16" if "story" in brief.formats else "1:1",
            "variants": 3 if brief.kind == "image" else 1,
            "overlay": {**overlay_for(brief), "formats": list(brief.formats)} if brief.kind == "image" else {},
        },
        "approval_binding": {
            "approval_reference": approval_reference,
            "approval_fingerprint": brief.approval_fingerprint,
            "creative_id": brief.creative_id, "campaign_id": brief.campaign_id,
        },
        "requires_canonical_execution": True,
        "requires_human_approval": True,
        "spend_authorized": False,
    }


# --- donor creative_studio: copy preflight and render idempotency ---
RISKY_CLAIMS = ("100% гаран", "гарантированно", "гарантия результата", "лучший в мире", "до/после", "исцел",
                "100% guarantee", "guaranteed cure", "guaranteed result", "best in the world", "before/after")


def preflight(headline: str, description: str) -> tuple[int, tuple[str, ...]]:
    """Donor creative_studio._preflight: risky claims block generation; long copy is penalised for layout.

    The donor typography check (prompt mentions the compositor) is structural here: AD_NEGATIVE_PROMPT
    always forbids inscriptions and copy is applied by the render-pack overlay.
    """
    issues: list[str] = []
    score = 100
    combined = f"{headline} {description}".casefold()
    if any(token in combined for token in RISKY_CLAIMS):
        issues.append("risky_claim")
        score -= 35
    if len(headline) > 90:
        issues.append("headline_long_for_layout")
        score -= 10
    if len(description) > 300:
        issues.append("body_long_for_layout")
        score -= 10
    return max(0, score), tuple(issues)


def overlay_for(brief: AdvertisingCreativeBrief) -> dict[str, object]:
    layout = "top_card" if brief.angle == "clear_process" else "lower_card"
    return {"headline": brief.headline, "body": brief.description, "cta": "Записаться", "layout": layout}


def render_idempotency_key(brief: AdvertisingCreativeBrief) -> str:
    """Same key shape the executor uses for the render pack (shared core helper)."""
    return render_pack_idempotency_key(brief.creative_id, overlay_for(brief), brief.formats)
