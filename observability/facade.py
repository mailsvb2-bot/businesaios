from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservabilitySurfaces:
    cross_cutting_root: str = "observ" "ability"
    runtime_surface: str = "runtime.observability"
    platform_surface: str = "observability.platform.observability"
    infrastructure_surface: str = "infrastructure.observability"
    core_surface: str = "core.observability"


def get_observability_surfaces() -> ObservabilitySurfaces:
    return ObservabilitySurfaces()


__all__ = ["ObservabilitySurfaces", "get_observability_surfaces"]
