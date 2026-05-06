from __future__ import annotations

from types import MappingProxyType
from typing import Mapping


def required_fields_schema(*fields: str) -> Mapping[str, tuple[str, ...]]:
    normalized = tuple(str(field).strip() for field in fields)
    if not normalized or any(not field for field in normalized):
        raise ValueError("schema fields must be non-empty")
    return MappingProxyType({'required': normalized})


def validate_required_fields(document: Mapping[str, object], required_fields: tuple[str, ...]) -> list[str]:
    return [field for field in required_fields if field not in document]
