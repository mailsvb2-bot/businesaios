from __future__ import annotations

"""Canonical runtime registration owner surface.

The package root owns runtime registration exports. Historical
``boot.registrations.register_*`` imports remain available through explicit
alias installation, while internal code should import from
``boot.registrations`` to prevent wrapper modules from acting like parallel
owners.
"""

from importlib import import_module
import sys
from types import ModuleType
from typing import Any, Final

from boot.runtime_service_specs import (
    CATALOG_BACKED_RUNTIME_CALLABLES,
    SINGLETON_RUNTIME_CALLABLES,
    build_registration_compat_exports,
)
from boot.registrations.register_action_executor import register_action_executor
from boot.registrations.register_decision_core import (
    register_decision_core,
    register_runtime_decision_execution_service,
)
from boot.registrations.register_governance import register_governance
from boot.registrations.simple_singletons import (
    register_action_budget,
    register_kill_switch,
    register_observability,
    register_reward,
    register_risk,
    register_simulation,
)

REGISTRATION_COMPAT_EXPORTS: Final[dict[str, str]] = build_registration_compat_exports(
    callable_names=SINGLETON_RUNTIME_CALLABLES,
)
REGISTRATION_CATALOG_COMPAT_EXPORTS: Final[dict[str, str]] = build_registration_compat_exports(
    callable_names=CATALOG_BACKED_RUNTIME_CALLABLES,
)
ALL_REGISTRATION_COMPAT_EXPORTS: Final[dict[str, str]] = {
    **REGISTRATION_COMPAT_EXPORTS,
    **REGISTRATION_CATALOG_COMPAT_EXPORTS,
}
CANON_REGISTRATION_COMPAT_SHIM: Final[bool] = True
CANON_REGISTRATION_OWNER: Final[bool] = True
CANON_REGISTRATION_DECISION_EXECUTION_EXPORT_OWNER: Final[bool] = True
SINGLETON_OWNER_MODULE: Final[str] = 'boot.registrations.simple_singletons'
CATALOG_OWNER_MODULE: Final[str] = 'boot.registrations._catalog_owner'

_PACKAGE_ALIAS_NAMES: Final[tuple[str, ...]] = (
    'catalog',
    'register_action_budget',
    'register_architecture_watch',
    'register_autonomy_advisor',
    'register_creative_intelligence',
    'register_decision_gateway',
    'register_decision_input_service',
    'register_diffusion_watch',
    'register_flow_watch',
    'register_kill_switch',
    'register_market_watch',
    'register_observability',
    'register_reward',
    'register_risk',
    'register_runtime_packet_provider',
    'register_runtime_state_enrichment',
    'register_simulation',
    'register_structure_watch',
    'register_world_state_integration',
)
_CATALOG_EXPORTS = [
    'CATALOG_REGISTRATION_FUNCTION_NAMES',
    'CATALOG_REGISTRATION_FUNCTIONS',
    'register_architecture_watch',
    'register_autonomy_advisor',
    'register_creative_intelligence',
    'register_decision_gateway',
    'register_decision_input_service',
    'register_diffusion_watch',
    'register_flow_watch',
    'register_market_watch',
    'register_runtime_packet_provider',
    'register_runtime_state_enrichment',
    'register_structure_watch',
    'register_world_state_integration',
]


def _load_catalog_owner() -> Any:
    return import_module(CATALOG_OWNER_MODULE)


def __getattr__(name: str) -> Any:
    if name in {
        'ALL_REGISTRATION_COMPAT_EXPORTS', 'CANON_REGISTRATION_COMPAT_SHIM', 'CANON_REGISTRATION_OWNER',
        'CANON_REGISTRATION_DECISION_EXECUTION_EXPORT_OWNER',
        'CATALOG_OWNER_MODULE', 'REGISTRATION_CATALOG_COMPAT_EXPORTS', 'REGISTRATION_COMPAT_EXPORTS',
        'SINGLETON_OWNER_MODULE'
    }:
        return globals()[name]
    if name in _CATALOG_EXPORTS:
        return getattr(_load_catalog_owner(), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_load_catalog_owner())))


def _install_package_alias_modules() -> None:
    owner = sys.modules[__name__]
    for alias_name in _PACKAGE_ALIAS_NAMES:
        qualified_name = f'{__name__}.{alias_name}'
        if qualified_name in sys.modules:
            continue
        alias_module = ModuleType(qualified_name)
        if alias_name == 'catalog':
            def _catalog_getattr(name: str, *, _owner=owner) -> Any:
                return getattr(_owner, name)

            def _catalog_dir(*, _owner=owner) -> list[str]:
                return sorted(set(dir(_owner)))

            alias_module.__getattr__ = _catalog_getattr  # type: ignore[attr-defined]
            alias_module.__dir__ = _catalog_dir  # type: ignore[attr-defined]
            alias_module.__all__ = [name for name in dir(owner) if not name.startswith('_')]
        else:
            exported = getattr(owner, alias_name)
            alias_module.__dict__[alias_name] = exported
            alias_module.__all__ = [alias_name]
        sys.modules[qualified_name] = alias_module


__all__ = [
    'ALL_REGISTRATION_COMPAT_EXPORTS',
    'CATALOG_REGISTRATION_FUNCTION_NAMES',
    'CATALOG_REGISTRATION_FUNCTIONS',
    'CANON_REGISTRATION_COMPAT_SHIM',
    'CANON_REGISTRATION_OWNER',
    'CANON_REGISTRATION_DECISION_EXECUTION_EXPORT_OWNER',
    'CATALOG_OWNER_MODULE',
    'REGISTRATION_CATALOG_COMPAT_EXPORTS',
    'REGISTRATION_COMPAT_EXPORTS',
    'SINGLETON_OWNER_MODULE',
    'register_action_budget',
    'register_action_executor',
    'register_architecture_watch',
    'register_autonomy_advisor',
    'register_creative_intelligence',
    'register_decision_core',
    'register_runtime_decision_execution_service',
    'register_decision_gateway',
    'register_decision_input_service',
    'register_diffusion_watch',
    'register_flow_watch',
    'register_governance',
    'register_kill_switch',
    'register_market_watch',
    'register_observability',
    'register_reward',
    'register_risk',
    'register_runtime_packet_provider',
    'register_runtime_state_enrichment',
    'register_simulation',
    'register_structure_watch',
    'register_world_state_integration',
]

_install_package_alias_modules()
