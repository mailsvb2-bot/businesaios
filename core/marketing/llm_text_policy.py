from __future__ import annotations

from core.llm.guardrails import enforce_single_message, forbid_phrases, require_max_chars
from core.llm.guardrails_ext import enforce_price_exact, forbid_manipulation_claims


def validate_marketing_text(*, text: str, max_chars: int, forbid: tuple, offer: dict | None) -> tuple[bool, str, str]:
    current = (text or "").strip()

    g1 = enforce_single_message(current)
    if not g1.ok:
        return False, current, "empty_or_multiline"
    current = g1.fixed_text or current

    g2 = forbid_phrases(current, list(forbid))
    if not g2.ok:
        return False, current, str(g2.reason or "forbidden_phrase")

    g3 = forbid_manipulation_claims(current)
    if not g3.ok:
        return False, current, str(g3.reason or "manipulation_claim")

    offer = offer or {}
    price = str(offer.get("price") or "")
    currency = str(offer.get("currency") or "")
    if price:
        g4 = enforce_price_exact(current, price=price, currency=currency)
        if not g4.ok:
            return False, current, str(g4.reason or "price_mismatch")
        current = g4.fixed_text or current

    g5 = require_max_chars(current, max_chars=int(max_chars))
    if not g5.ok:
        return False, current, str(g5.reason or "too_long")
    current = g5.fixed_text or current

    return True, current, ""


def err_code(exc: Exception) -> str:
    return exc.__class__.__name__.lower()[:64]
