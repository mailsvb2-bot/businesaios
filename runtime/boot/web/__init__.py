from __future__ import annotations

"""Canonical runtime web package root.

The package root intentionally stays thin. Internal code should import concrete
owner surfaces from runtime.boot.web submodules instead of relying on package-
root re-export sprawl.
"""

from shared.package_submodule_alias import install_package_submodule_alias

CANON_RUNTIME_WEB_OWNER_SURFACE = True
CANON_RUNTIME_WEB_ALIAS_NAMESPACE = True
CANON_RUNTIME_WEB_COMPONENT_CLUSTER_COLLAPSE = True
CANON_BOOT_WIRING_ONLY = True

_PUBLIC_API_MODULES = (
    "public_api_bundles",
    "public_api_frameworks",
    "public_api_graphs",
    "public_api_observability",
    "public_api_runtime",
    "public_api_services",
    "public_api_settings",
)

for _module_name in _PUBLIC_API_MODULES:
    install_package_submodule_alias(__name__, _module_name)

__all__ = [
    'CANON_BOOT_WIRING_ONLY',
    'CANON_RUNTIME_WEB_ALIAS_NAMESPACE',
    'CANON_RUNTIME_WEB_COMPONENT_CLUSTER_COLLAPSE',
    'CANON_RUNTIME_WEB_OWNER_SURFACE',
]
