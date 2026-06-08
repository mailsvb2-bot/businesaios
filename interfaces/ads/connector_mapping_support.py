from __future__ import annotations

from datetime import date
from typing import Any
from collections.abc import Sequence

from .base import AdsConnectorError


def parse_metric_day(*, row: dict[str, Any], candidate_keys: Sequence[str], connector_name: str) -> date:
    for key in candidate_keys:
        raw = row.get(key)
        if isinstance(raw, date):
            return raw
        if raw is None:
            continue
        try:
            return date.fromisoformat(str(raw))
        except Exception:
            continue
    raise AdsConnectorError(f"{connector_name}: metric row missing valid day")


def parse_optional_budget(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except Exception:
            continue
    return None



def resolve_first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None

def resolve_first_nonempty(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return str(default)


__all__ = [
    "parse_metric_day",
    "parse_optional_budget",
    "resolve_first_nonempty",
    "resolve_first_present",
]
