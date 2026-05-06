from __future__ import annotations

"""Canonical namespace alias map.

These aliases document historical package names that are allowed to exist only
as compatibility shells. New business logic should target the canonical path.
"""

from typing import Final

CANONICAL_NAMESPACE_ALIASES: Final[dict[str, str]] = {
    "core.products": "core.product",
    "core.decision": "core.decisioning",
    "core.learning": "core.learning_loop",
    "infrastructure": "infra",
}


def canonical_namespace_for(name: str) -> str:
    normalized = str(name).strip()
    return CANONICAL_NAMESPACE_ALIASES.get(normalized, normalized)


__all__ = ["CANONICAL_NAMESPACE_ALIASES", "canonical_namespace_for"]
