from __future__ import annotations

"""Canonical runtime factory owner surface.

The package root owns runtime factory exports. Historical ``boot.factories.*``
module imports remain available through explicit alias installation, while
internal code should import from ``boot.factories`` to avoid catalog-shaped
surface fragmentation.
"""

from importlib import import_module
import sys
from types import ModuleType
from typing import Any, Final

from boot.factories.action_executor_factory import build_action_executor
from boot.factories.decision_core_factory import (
    build_decision_core,
    build_runtime_decision_execution_service,
)
from boot.factories.governance_chain_factory import build_governance_chain

from boot.factories.inference_capacity_router_factory import build_inference_capacity_router
from boot.factories.inference_dispatch_orchestrator_factory import build_inference_dispatch_orchestrator
from boot.factories.inference_provider_factory import build_inference_provider_registry

CANON_FACTORY_COMPAT_SHIM: Final[bool] = True
CANON_FACTORY_OWNER: Final[bool] = True
CANON_FACTORY_DECISION_EXECUTION_EXPORT_OWNER: Final[bool] = True
FACTORY_OWNER_MODULE: Final[str] = 'boot.factories._catalog_owner'
FACTORY_COMPAT_EXPORTS: Final[dict[str, str]] = {
    'build_architecture_watch_service': 'architecture_watch',
    'build_autonomy_advisor_service': 'autonomy_advisor',
    'build_creative_intelligence_service': 'creative_intelligence',
    'build_decision_gateway': 'decision_gateway',
    'build_runtime_decision_execution_service': 'decision_core_factory',
    'build_decision_input_service': 'decision_input_service',
    'build_diffusion_watch_service': 'diffusion_watch',
    'build_flow_watch_service': 'flow_watch',
    'build_market_watch_service': 'market_watch',
    'build_runtime_packet_provider': 'runtime_packet_provider',
    'build_runtime_state_enrichment_service': 'runtime_state_enrichment',
    'build_structure_watch_service': 'structure_watch',
    'build_world_state_integration_service': 'world_state_integration',
}
_FACTORY_EXPORT_NAMES = [
    'FACTORY_FUNCTIONS',
    'FACTORY_SERVICE_NAMES',
    'LOCAL_FACTORY_FUNCTION_NAMES',
    'build_runtime_decision_factory_bundle',
    'get_factory_for_service',
    *FACTORY_COMPAT_EXPORTS.keys(),
]
_PACKAGE_ALIAS_NAMES: Final[tuple[str, ...]] = ('catalog',)


def _owner() -> Any:
    return import_module(FACTORY_OWNER_MODULE)


def __getattr__(name: str) -> Any:
    if name in {'CANON_FACTORY_COMPAT_SHIM', 'CANON_FACTORY_OWNER', 'CANON_FACTORY_DECISION_EXECUTION_EXPORT_OWNER', 'FACTORY_OWNER_MODULE', 'FACTORY_COMPAT_EXPORTS'}:
        return globals()[name]
    if name in _FACTORY_EXPORT_NAMES:
        return getattr(_owner(), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_owner())))


def _install_package_alias_modules() -> None:
    owner = sys.modules[__name__]
    for alias_name in _PACKAGE_ALIAS_NAMES:
        qualified_name = f'{__name__}.{alias_name}'
        if qualified_name in sys.modules:
            continue
        alias_module = ModuleType(qualified_name)

        def _alias_getattr(name: str, *, _owner=owner) -> Any:
            return getattr(_owner, name)

        def _alias_dir(*, _owner=owner) -> list[str]:
            return sorted(set(dir(_owner)))

        alias_module.__getattr__ = _alias_getattr  # type: ignore[attr-defined]
        alias_module.__dir__ = _alias_dir  # type: ignore[attr-defined]
        alias_module.__all__ = [name for name in dir(owner) if not name.startswith('_')]
        sys.modules[qualified_name] = alias_module


__all__ = [
    'CANON_FACTORY_COMPAT_SHIM',
    'CANON_FACTORY_OWNER',
    'CANON_FACTORY_DECISION_EXECUTION_EXPORT_OWNER',
    'FACTORY_COMPAT_EXPORTS',
    'FACTORY_FUNCTIONS',
    'FACTORY_OWNER_MODULE',
    'FACTORY_SERVICE_NAMES',
    'LOCAL_FACTORY_FUNCTION_NAMES',
    'build_action_executor',
    'build_architecture_watch_service',
    'build_autonomy_advisor_service',
    'build_creative_intelligence_service',
    'build_decision_core',
    'build_decision_gateway',
    'build_runtime_decision_execution_service',
    'build_runtime_decision_factory_bundle',
    'build_decision_input_service',
    'build_diffusion_watch_service',
    'build_flow_watch_service',
    'build_governance_chain',
    'build_inference_capacity_router',
    'build_inference_dispatch_orchestrator',
    'build_inference_provider_registry',
    'get_factory_for_service',
    'build_market_watch_service',
    'build_runtime_packet_provider',
    'build_runtime_state_enrichment_service',
    'build_structure_watch_service',
    'build_world_state_integration_service',
]


_install_package_alias_modules()
