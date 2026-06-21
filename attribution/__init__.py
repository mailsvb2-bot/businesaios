from __future__ import annotations

"""Canonical attribution surface.

This namespace owns attribution/provenance interpretation only. Historical
module-level import paths remain available as explicit compat modules so we can
collapse wrapper fleets without reintroducing a second registry or business
logic path.
"""

from importlib import import_module
from pathlib import Path
import sys
import types
from typing import Any

CANON_ATTRIBUTION_OWNER_SURFACE = True
CANON_ATTRIBUTION_COMPAT_SHIM = True
CANON_ATTRIBUTION_PROVENANCE_NAMESPACE = True
_OWNER_MODULE = "attribution.catalog"


def _owner() -> Any:
    return import_module(_OWNER_MODULE)


ATTRIBUTION_COMPAT_EXPORTS = {
    'AttributionAudit': 'attribution_audit',
    'AttributionEngine': 'attribution_engine',
    'CampaignRevenueLinker': 'campaign_revenue_linker',
    'FirstTouchModel': 'first_touch_model',
    'LastTouchModel': 'last_touch_model',
    'LeadToRevenueResolver': 'lead_to_revenue_resolver',
    'MultiTouchModel': 'multi_touch_model',
    'OfflineConversionMapper': 'offline_conversion_mapper',
    'TouchpointRegistry': 'touchpoint_registry',
}


# Historical marker for arch tests: _install_compat_aliases()
def _install_compat_aliases() -> None:
    owner = _owner()
    package_name = __name__
    for export_name, module_name in ATTRIBUTION_COMPAT_EXPORTS.items():
        qualified_name = f"{package_name}.{module_name}"
        module = types.ModuleType(qualified_name)
        value = getattr(owner, export_name)
        module.__dict__.update({
            export_name: value,
            '__all__': [export_name],
            '__file__': str(Path(__file__).with_name(f"{module_name}.py")),
            '__package__': package_name,
            '__doc__': f'Compat alias for {qualified_name}',
        })
        sys.modules[qualified_name] = module
        globals()[module_name] = module


_install_compat_aliases()


__all__ = [
    'ATTRIBUTION_COMPAT_EXPORTS',
    'CANON_ATTRIBUTION_COMPAT_SHIM',
    'CANON_ATTRIBUTION_OWNER_SURFACE',
    'CANON_ATTRIBUTION_PROVENANCE_NAMESPACE',
    'AttributionAudit',
    'AttributionEngine',
    'CampaignRevenueLinker',
    'FirstTouchModel',
    'LastTouchModel',
    'LeadToRevenueResolver',
    'MultiTouchModel',
    'OfflineConversionMapper',
    'TouchpointRegistry',
]


def __getattr__(name: str) -> Any:
    if name in {
        'ATTRIBUTION_COMPAT_EXPORTS',
        'CANON_ATTRIBUTION_OWNER_SURFACE',
        'CANON_ATTRIBUTION_COMPAT_SHIM',
        'CANON_ATTRIBUTION_PROVENANCE_NAMESPACE',
    }:
        return globals()[name]
    if name in __all__:
        return getattr(_owner(), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_owner())))
