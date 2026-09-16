from __future__ import annotations

CANON_LEAD_FACT_VOCABULARY = True

LEAD_CREATED = "lead.created"
LEAD_UPDATED = "lead.updated"
LEAD_ARCHIVED = "lead.archived"
LEAD_FACT_TYPES = frozenset({LEAD_CREATED, LEAD_UPDATED, LEAD_ARCHIVED})

__all__ = [
    "CANON_LEAD_FACT_VOCABULARY",
    "LEAD_ARCHIVED",
    "LEAD_CREATED",
    "LEAD_FACT_TYPES",
    "LEAD_UPDATED",
]
