from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrmNote:
    body: str
    linked_object_type: str
    linked_object_id: str
