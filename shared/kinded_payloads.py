from __future__ import annotations

from typing import Any, Mapping


def clone_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload or {})


def build_kinded_payload(kind: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized_kind = str(kind or '').strip()
    if not normalized_kind:
        raise ValueError('kind must be non-empty')
    return {'kind': normalized_kind, 'payload': clone_payload(payload)}


class KindedPayloadService:
    KIND: str = ''

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        normalized_kind = str(getattr(cls, 'KIND', '')).strip()
        if not normalized_kind:
            raise TypeError(f'{cls.__name__} must define non-empty KIND')

    def build_payload(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        return build_kinded_payload(self.KIND, payload)
