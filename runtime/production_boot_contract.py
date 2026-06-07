from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class ProductionBootStatus(str, Enum):
    CONTRACT_SATISFIED = "contract_satisfied"
    BLOCKED = "blocked"
    ADVISORY_ONLY = "advisory_only"


_PLACEHOLDER_MARKERS = (
    "change-me",
    "replace_with",
    "placeholder",
    "example",
    "dummy",
    "todo",
)


@dataclass(frozen=True)
class ProductionBootProbe:
    env: str
    app_profile: str
    database_url_present: bool
    postgres_enabled: bool
    migrations_required: bool
   