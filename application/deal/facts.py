from __future__ import annotations

CANON_DEAL_FACT_VOCABULARY = True

DEAL_CREATED = "deal.created"
DEAL_UPDATED = "deal.updated"
DEAL_ARCHIVED = "deal.archived"
DEAL_FACT_TYPES = frozenset({DEAL_CREATED, DEAL_UPDATED, DEAL_ARCHIVED})

__all__ = [
    "CANON_DEAL_FACT_VOCABULARY",
    "DEAL_ARCHIVED",
    "DEAL_CREATED",
    "DEAL_FACT_TYPES",
    "DEAL_UPDATED",
]
