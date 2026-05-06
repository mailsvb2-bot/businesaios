from __future__ import annotations

from typing import Any


class KindedPayloadBuilder:
    """Single payload-building primitive for thin web pages and components."""

    KIND: str = ''

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        kind = str(getattr(cls, 'KIND', '')).strip()
        if not kind:
            raise TypeError(f"{cls.__name__} must define non-empty KIND")

    def build(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {'kind': self.KIND, 'payload': dict(payload)}
