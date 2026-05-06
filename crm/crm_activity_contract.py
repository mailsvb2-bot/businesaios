from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmActivity:
    activity_type: str
    subject: str
    linked_object_type: str
    linked_object_id: str
    metadata: Mapping[str, object] = field(default_factory=dict)
