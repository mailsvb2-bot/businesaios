from __future__ import annotations

ALLOWED_DEPENDENCIES = {
    "evaluation": {"contracts", "data", "safety", "observability"},
    "training": {"contracts", "data", "storage", "observability"},
    "safety": {"contracts", "observability"},
}

__all__ = [
    "ALLOWED_DEPENDENCIES",
]
