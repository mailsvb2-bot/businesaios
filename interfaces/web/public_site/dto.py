from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PublicCapabilityPayload:
    id: str
    title: str
    status: str
    connectable: bool
    roadmap_only: bool
    evidence: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class PublicSitePayload:
    version: str
    sections: Mapping[str, Any]
    capabilities: Mapping[str, Any]
    publication: Mapping[str, Any]


__all__ = ['PublicCapabilityPayload', 'PublicSitePayload']
