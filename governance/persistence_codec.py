from __future__ import annotations

"""Canonical JSON codec for governance persistence surfaces.

This module stores governance state as plain data only.
It must never contain decision logic.
"""

import json
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypeVar, get_args, get_origin, get_type_hints


CANON_GOVERNANCE_PERSISTENCE_CODEC = True

T = TypeVar("T")


def ensure_parent_dir(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_json(path: Path, payload: object) -> None:
    path = ensure_parent_dir(Path(path))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def read_json_or_default(path: Path, *, default: object) -> object:
    p = Path(path)
    if not p.exists():
        return default
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {name: to_jsonable(getattr(value, name)) for name in value.__dataclass_fields__.keys()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    return value


def from_dataclass(cls: type[T], payload: dict[str, Any]) -> T:
    kwargs: dict[str, Any] = {}
    hints = get_type_hints(cls)
    for field in fields(cls):
        if field.name not in payload:
            continue
        kwargs[field.name] = _coerce_value(hints.get(field.name, field.type), payload[field.name])
    return cls(**kwargs)


def _coerce_value(tp: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(tp)
    if origin is None:
        if tp is Any:
            return value
        if isinstance(tp, type) and issubclass(tp, Enum):
            return tp(value)
        if tp is datetime:
            return datetime.fromisoformat(value)
        if isinstance(tp, type) and is_dataclass(tp):
            return from_dataclass(tp, value)
        return value

    if origin in (list, tuple, set, frozenset):
        item_types = get_args(tp)
        item_type = item_types[0] if item_types else Any
        items = [_coerce_value(item_type, item) for item in value]
        if origin is list:
            return list(items)
        if origin is tuple:
            return tuple(items)
        if origin is set:
            return set(items)
        return frozenset(items)

    if origin is dict:
        key_type, value_type = get_args(tp) if get_args(tp) else (Any, Any)
        return {
            _coerce_value(key_type, k): _coerce_value(value_type, v)
            for k, v in value.items()
        }

    if origin is Callable:
        return value

    args = [arg for arg in get_args(tp) if arg is not type(None)]
    if len(args) == 1:
        return _coerce_value(args[0], value)
    return value


__all__ = [
    "CANON_GOVERNANCE_PERSISTENCE_CODEC",
    "atomic_write_json",
    "ensure_parent_dir",
    "from_dataclass",
    "read_json_or_default",
    "to_jsonable",
]
