from __future__ import annotations

"""Canonical template/fallback surface for marketing messaging."""

from core.marketing.fallback_copy import compose_fallback_message


def compose_marketing_fallback(*, offer: dict, locale: str) -> str:
    return compose_fallback_message(offer or {}, locale=locale)
