from __future__ import annotations

"""Canonical growth-engine payload and package contract.

This module keeps Growth package assembly in one place so campaign / creative /
budget engines do not each invent their own mini-contracts.
"""

from dataclasses import dataclass
from typing import Mapping

GROWTH_PLAN_KIND = "growth_plan"
CAMPAIGN_ENGINE_PACKAGE_KIND = "campaign_engine_package"
CREATIVE_ENGINE_PACKAGE_KIND = "creative_engine_package"
BUDGET_ENGINE_PACKAGE_KIND = "budget_engine_package"
SEO_ENGINE_PACKAGE_KIND = "seo_engine_package"
PLATFORM_ENGINE_PACKAGE_KIND = "platform_engine_package"


@dataclass(frozen=True)
class EngineArtifact:
    kind: str
    payload: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "payload": dict(self.payload)}


@dataclass(frozen=True)
class EnginePackage:
    kind: str
    payload: dict[str, object]
    sections: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "payload": dict(self.payload), **dict(self.sections)}


def normalize_payload(payload: Mapping[str, object] | None) -> dict[str, object]:
    return dict(payload or {})


def build_artifact(kind: str, payload: Mapping[str, object] | None) -> dict[str, object]:
    return EngineArtifact(kind=str(kind), payload=normalize_payload(payload)).as_dict()


def build_package(
    kind: str,
    payload: Mapping[str, object] | None,
    **sections: object,
) -> dict[str, object]:
    return EnginePackage(
        kind=str(kind),
        payload=normalize_payload(payload),
        sections=dict(sections),
    ).as_dict()


__all__ = [
    "BUDGET_ENGINE_PACKAGE_KIND",
    "CAMPAIGN_ENGINE_PACKAGE_KIND",
    "CREATIVE_ENGINE_PACKAGE_KIND",
    "EngineArtifact",
    "EnginePackage",
    "GROWTH_PLAN_KIND",
    "PLATFORM_ENGINE_PACKAGE_KIND",
    "SEO_ENGINE_PACKAGE_KIND",
    "build_artifact",
    "build_package",
    "normalize_payload",
]
