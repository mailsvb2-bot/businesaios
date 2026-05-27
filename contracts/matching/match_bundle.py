from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MatchBundle:
    request_id: str = ""
    candidates: tuple[object, ...] = ()
    audit: dict[str, object] = field(default_factory=dict)
