from __future__ import annotations

CANON_COMPAT_SHIM = True
from dataclasses import dataclass, field
from typing import Any, Dict
from shared.types import ensure_jsonable, new_id, utc_now


@dataclass(frozen=True)
class Event:
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id('evt'))
    created_at: object = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.event_type.strip() != self.event_type or not self.event_type:
            raise ValueError('event_type must be non-empty and normalized')
        object.__setattr__(self, 'payload', ensure_jsonable(self.payload))

    def as_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'created_at': ensure_jsonable(self.created_at),
            'payload': ensure_jsonable(self.payload),
        }
