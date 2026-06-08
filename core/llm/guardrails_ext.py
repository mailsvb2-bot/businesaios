from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailResult:
    ok: bool
    reason: str = ""
    fixed_text: str | None = None


_RE_URGENCY = re.compile(r"\b(только сегодня|последний шанс|срочно|немедленно|акция закончится)\b", re.I)
_RE_GUARANTEE = re.compile(r"\b(гарантирую|100%|точно поможет|вылечит|избавит навсегда)\b", re.I)
_RE_MEDICAL = re.compile(r"\b(диагноз|лечение|врач|лекарство|вылеч)\b", re.I)


def forbid_manipulation_claims(text: str) -> GuardrailResult:
    if _RE_URGENCY.search(text or ""):
        return GuardrailResult(ok=False, reason="urgency_manipulation")
    if _RE_GUARANTEE.search(text or ""):
        return GuardrailResult(ok=False, reason="guarantee_claim")
    if _RE_MEDICAL.search(text or ""):
        return GuardrailResult(ok=False, reason="medical_claim")
    return GuardrailResult(ok=True)


def enforce_price_exact(text: str, *, price: str, currency: str) -> GuardrailResult:
    """If offer is paid: require exact price+currency substring.

    Prevents hallucinated pricing.
    """

    if not (price or "").strip():
        return GuardrailResult(ok=True)
    needle = f"{price}{currency}".replace(" ", "")
    hay = (text or "").replace(" ", "")
    if needle and needle not in hay:
        return GuardrailResult(ok=False, reason="price_mismatch")
    return GuardrailResult(ok=True)
