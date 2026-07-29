from __future__ import annotations

"""Canonical attribution compatibility surface.

All attribution behavior is owned by :mod:`attribution.catalog`. Historical
submodule import paths are ordinary physical re-export modules, so packaging,
introspection and static analysis observe the same structure that Python runs.
"""

from importlib import import_module
from typing import Any

from attribution.catalog import ATTRIBUTION_COMPAT_EXPORTS


CANON_ATTRIBUTION_OWNER_SURFACE = True
CANON_ATTRIBUTION_COMPAT_SHIM = True
CANON_ATTRIBUTION_PROVENANCE_NAMESPACE = True
_OWNER_MODULE = "attribution.catalog"


def _owner() -> Any:
    return import_module(_OWNER_MODULE)



__all__ = [
    "ATTRIBUTION_COMPAT_EXPORTS",
    "CANON_ATTRIBUTION_COMPAT_SHIM",
    "CANON_ATTRIBUTION_OWNER_SURFACE",
    "CANON_ATTRIBUTION_PROVENANCE_NAMESPACE",
    "AttributionAudit",
    "AttributionEngine",
    "CampaignRevenueLinker",
    "FirstTouchModel",
    "LastTouchModel",
    "LeadToRevenueResolver",
    "MultiTouchModel",
    "OfflineConversionMapper",
    "TouchpointRegistry",
]


def __getattr__(name: str) -> Any:
    if name in {
        "ATTRIBUTION_COMPAT_EXPORTS",
        "CANON_ATTRIBUTION_OWNER_SURFACE",
        "CANON_ATTRIBUTION_COMPAT_SHIM",
        "CANON_ATTRIBUTION_PROVENANCE_NAMESPACE",
    }:
        return globals()[name]
    if name in __all__:
        return getattr(_owner(), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_owner())))
