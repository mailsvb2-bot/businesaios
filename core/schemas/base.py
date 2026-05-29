from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class SchemaId:
    name: str
    version: int


class Schema:
    """
    Каноническая схема.
    Должна быть чистой, детерминированной и без side-effects.
    """

    def validate(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Приведение к канонической форме для replay/ML.
        """
        raise NotImplementedError
