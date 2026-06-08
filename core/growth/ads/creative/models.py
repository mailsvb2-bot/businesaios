from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CreativeGuardrails:
    """
    Guardrails for ad creatives. These are intentionally conservative defaults.
    They should be extended/overridden per-tenant/product via catalogs.
    """

    max_headline_len: int = 60
    max_primary_text_len: int = 200
    max_description_len: int = 90

    disallow_all_caps: bool = True
    disallow_excessive_punct: bool = True
    disallow_shaming_language: bool = True
    disallow_medical_claims: bool = True  # keep safe for broad categories

    # Optional deny phrases / patterns (lowercased contains)
    deny_phrases: list[str] = field(default_factory=lambda: ["100% гарантия", "лучший в мире"])


@dataclass(frozen=True)
class CreativeCandidate:
    creative_id: str
    offer_arm: str
    headline: str
    primary_text: str
    description: str = ""
    cta: str = "Learn More"
    meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CreativeSelection:
    selected: CreativeCandidate
    reason: str
    scores: dict[str, float]
    guardrails_ok: bool
