from __future__ import annotations

from typing import Iterable

FORBIDDEN_CAPABILITIES_OUTSIDE_CORE = (
    "choose",
    "select_best",
    "finalize",
    "issue_final",
    "resolve_final",
)

ALLOWED_ADVISORY_CAPABILITIES = (
    "score",
    "observe",
    "rank",
    "validate",
    "recommend",
    "guard",
    "explain",
    "enrich",
    "project",
    "build",
)


def contains_forbidden_capability_name(names: Iterable[str]) -> bool:
    lowered = [str(x).strip().lower() for x in names]
    return any(name in FORBIDDEN_CAPABILITIES_OUTSIDE_CORE for name in lowered)
