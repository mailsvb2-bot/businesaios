from __future__ import annotations
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def new_id(prefix: str) -> str:
    normalized = prefix.strip().replace(' ', '_') or 'id'
    return f"{normalized}_{uuid.uuid4().hex[:12]}"


def ensure_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return ensure_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): ensure_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [ensure_jsonable(item) for item in value]
    return value


def frozen_dict(mapping: Mapping[str, Any] | None = None, **extra: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    if mapping:
        merged.update({str(key): ensure_jsonable(value) for key, value in mapping.items()})
    merged.update({str(key): ensure_jsonable(value) for key, value in extra.items()})
    return merged


@dataclass(frozen=True)
class Record:
    record_id: str = field(default_factory=lambda: new_id('rec'))
    created_at: datetime = field(default_factory=utc_now)

    def as_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        return ensure_jsonable(payload)
