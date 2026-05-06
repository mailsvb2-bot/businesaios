from __future__ import annotations

"""Canonical optimization objective.

Project rule: execution contracts may expose domain-specific targets,
but the default business objective must be normalized in one place to avoid
synonymous strings and hidden second-brain drift.
"""

DEFAULT_OBJECTIVE = "profit"
ALLOWED_OBJECTIVES = frozenset({"profit", "leads", "traffic"})


def normalize_objective(raw: object, *, default: str = DEFAULT_OBJECTIVE) -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return default
    aliases = {
        "revenue": "profit",
        "sales": "profit",
        "roi": "profit",
        "conversions": "leads",
        "conversion": "leads",
        "reach": "traffic",
        "clicks": "traffic",
    }
    value = aliases.get(value, value)
    if value not in ALLOWED_OBJECTIVES:
        return default
    return value
