from __future__ import annotations

from typing import Any, Mapping


def require_mapping(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("INVALID_PAYLOAD")
    return payload


def required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        raise ValueError(f"MISSING_{key.upper()}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"EMPTY_{key.upper()}")
    return text


def required_int(payload: Mapping[str, Any], key: str, *, min_value: int | None = None) -> int:
    if key not in payload:
        raise ValueError(f"MISSING_{key.upper()}")
    try:
        value = int(payload.get(key))
    except Exception as exc:
        raise ValueError(f"INVALID_{key.upper()}") from exc
    if min_value is not None and value < min_value:
        raise ValueError(f"INVALID_{key.upper()}")
    return value


def optional_str(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def optional_dict(payload: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else None


def clamp_int(value: int, *, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, int(value)))
