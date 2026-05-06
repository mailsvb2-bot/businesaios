from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


def _payload_view(payload: object) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    if hasattr(payload, 'payload') and isinstance(getattr(payload, 'payload'), Mapping):
        body = dict(getattr(payload, 'payload'))
        action_type = getattr(payload, 'action_type', None)
        if action_type is not None:
            body.setdefault('action_type', str(action_type))
        return body
    return {}


def _as_float(value: object, *, default: float = 0.0, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    if minimum is not None and number < minimum:
        number = minimum
    if maximum is not None and number > maximum:
        number = maximum
    return number


def _as_int(value: object, *, default: int = 0, minimum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    if minimum is not None and number < minimum:
        number = minimum
    return number


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = str(value or '').strip().lower()
    return token in {'1', 'true', 'yes', 'y', 'on'}


def _as_text(value: object) -> str:
    return str(value or '').strip()


def _action_type(payload: Mapping[str, Any]) -> str:
    return _as_text(payload.get('action_type') or payload.get('action'))


def _channels(payload: Mapping[str, Any]) -> tuple[str, ...]:
    raw = payload.get('allowed_channels') or payload.get('safe_channels') or ()
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, Iterable):
        items = list(raw)
    else:
        items = []
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        token = _as_text(item).lower()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result)


@dataclass(frozen=True)
class GuardCheckResult:
    allowed: bool
    reason: str

    def as_tuple(self) -> tuple[bool, str]:
        return bool(self.allowed), str(self.reason)
