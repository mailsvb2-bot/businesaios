from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _jsonable_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def canonicalize_trace(trace: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(trace or {})
    items: list[tuple[str, Any]] = []
    for key in sorted(source):
        value = source[key]
        if isinstance(value, Mapping):
            value = canonicalize_mapping(value)
        elif isinstance(value, (list, tuple, set)):
            value = tuple(_jsonable_scalar(item) for item in value)
        else:
            value = _jsonable_scalar(value)
        items.append((str(key), value))
    return dict(items)


def canonicalize_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(payload or {})
    result: dict[str, Any] = {}
    for key in sorted(source):
        value = source[key]
        normalized_key = str(key)
        if normalized_key == "trace":
            result[normalized_key] = canonicalize_trace(value if isinstance(value, Mapping) else {})
            continue
        if isinstance(value, Mapping):
            result[normalized_key] = canonicalize_mapping(value)
        elif isinstance(value, (list, tuple, set)):
            result[normalized_key] = tuple(_jsonable_scalar(item) for item in value)
        else:
            result[normalized_key] = _jsonable_scalar(value)
    return result


@dataclass(frozen=True)
class CanonicalObservation:
    payload: dict[str, Any]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "CanonicalObservation":
        return cls(payload=canonicalize_mapping(payload))

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)
