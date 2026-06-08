from __future__ import annotations

import re

from .models import CreativeCandidate, CreativeGuardrails

_RE_EXCESSIVE_PUNCT = re.compile(r"([!?])\1\1+")


def _is_all_caps(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    return all(c.isupper() for c in letters)


def _contains_shaming(s: str) -> bool:
    # Conservative deny-list for broad safety; extend per domain if needed
    x = s.lower()
    deny = [
        "стыдно",
        "позор",
        "ты виноват",
        "ты плохой",
        "ленивый",
        "слабак",
    ]
    return any(d in x for d in deny)


def _contains_medical_claims(s: str) -> bool:
    # Conservative deny-list: avoid strong medical guarantees
    x = s.lower()
    deny = [
        "вылечим",
        "лечит",
        "исцеляет",
        "гарантированно вылечит",
        "без побочных эффектов",
    ]
    return any(d in x for d in deny)


def validate_creative(
    c: CreativeCandidate,
    g: CreativeGuardrails,
) -> tuple[bool, str]:
    # Length checks
    if len(c.headline) > g.max_headline_len:
        return False, "headline_too_long"
    if len(c.primary_text) > g.max_primary_text_len:
        return False, "primary_text_too_long"
    if len(c.description) > g.max_description_len:
        return False, "description_too_long"

    text_all = " ".join([c.headline, c.primary_text, c.description]).strip()

    if g.disallow_all_caps and (_is_all_caps(c.headline) or _is_all_caps(c.primary_text)):
        return False, "all_caps_disallowed"

    if g.disallow_excessive_punct and _RE_EXCESSIVE_PUNCT.search(text_all):
        return False, "excessive_punctuation"

    if g.disallow_shaming_language and _contains_shaming(text_all):
        return False, "shaming_language"

    if g.disallow_medical_claims and _contains_medical_claims(text_all):
        return False, "medical_claims"

    low = text_all.lower()
    for ph in g.deny_phrases:
        if ph.lower() in low:
            return False, "deny_phrase"

    return True, "ok"
