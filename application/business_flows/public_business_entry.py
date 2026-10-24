"""Public website lead capture (port of donor public_business_entry).

Pure: resolves the public token, validates the form and returns one ``lead_inbound``
``sales_pipeline@v1`` fact. Customer cards go only through injected canonical CRM
callables (executor ``ensure_customer_identity``); nothing here writes or sends.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from application.business_flows.customer_menu import token_uuid, uuid_token
from application.business_flows.projection import stable_id
from contracts.customer import normalize_customer_subject

CANON_PUBLIC_BUSINESS_ENTRY = True


def bounded(value: object, *, maximum: int) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    if len(text) > maximum:
        raise ValueError("public business entry value is too long")
    return text


def resolve_entry(business_token: str, *, business_active: Callable[[str], bool]) -> str:
    try:
        business_id = token_uuid(str(business_token or "").strip())
    except (TypeError, ValueError):
        raise ValueError("public business entry is invalid") from None
    if not business_active(business_id):
        raise ValueError("public business entry is unavailable")
    return business_id


def entry_url(*, public_base_url: str, business_id: str) -> str:
    base = str(public_base_url or "").strip().rstrip("/")
    if not base.startswith("https://") or " " in base:
        raise ValueError("public_base_url must be HTTPS")
    return f"{base}/clientplatform/b/{uuid_token(business_id)}"


def capture_lead(
    sales_payloads: list[dict[str, Any]], *, business_token: str, display_name: str,
    email: str | None, phone: str | None, source: str | None = None, campaign_ref: str | None = None,
    business_active: Callable[[str], bool],
    find_customer: Callable[[str, str], str | None],
    ensure_customer: Callable[..., str],
) -> tuple[dict[str, str], dict[str, Any] | None]:
    """Form submission -> canonical customer + one replay-safe inbound lead fact."""
    business_id = resolve_entry(business_token, business_active=business_active)
    name = bounded(display_name, maximum=200)
    if not name:
        raise ValueError("display_name is required")
    raw_email, raw_phone = bounded(email, maximum=320), bounded(phone, maximum=40)
    if not raw_email and not raw_phone:
        raise ValueError("email or phone is required")
    idents: list[tuple[str, str]] = []
    if raw_email:
        _, em = normalize_customer_subject("email", raw_email)
        if "@" not in em or em.startswith("@") or em.endswith("@"):
            raise ValueError("email is invalid")
        idents.append(("email", em))
    if raw_phone:
        idents.append(normalize_customer_subject("phone", raw_phone))
    matched = {cid for ch, s in idents if (cid := find_customer(ch, s))}
    if len(matched) > 1:
        raise ValueError("submitted contacts belong to different customers")
    customer_id = next(iter(matched), None)
    for ch, s in idents:
        customer_id = ensure_customer(channel=ch, external_subject=s, display_name=name,
                                      customer_id=customer_id)
    assert customer_id is not None
    stable = f"{idents[0][0]}:{idents[0][1]}"
    key = f"website-form-submit:{stable}"
    seen = {str(p.get("dedupe_key")) for p in sales_payloads if p.get("step") == "lead_inbound"}
    fact = None if key in seen else {
        "step": "lead_inbound", "lead_id": stable_id("lead", f"website-form:{stable}"),
        "name": name[:80], "source": "website", "surface": "public_business_entry",
        "customer_id": customer_id, "dedupe_key": key,
        "origin": bounded(source, maximum=120) or "business_page",
        "campaign_ref": bounded(campaign_ref, maximum=200),
    }
    return {"business_id": business_id, "customer_id": customer_id}, fact


__all__ = ["CANON_PUBLIC_BUSINESS_ENTRY", "bounded", "capture_lead", "entry_url", "resolve_entry"]
