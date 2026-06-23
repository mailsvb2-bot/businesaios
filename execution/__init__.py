from __future__ import annotations

"""Canonical execution package root.

The package root is the single execution owner surface. ``execution.public_api``
remains available only as a compatibility shell for historical imports.
"""

from importlib import import_module
from typing import Any

from canon.public_api_alias import install_public_api_alias

CANON_EXECUTION_PACKAGE_OWNER = True
CANON_EXECUTION_PUBLIC_API = True
CANON_EXECUTION_PUBLIC_API_COMPAT_SHELL = True
CANON_EXECUTION_COMPAT_SHIM = True
CANON_EXECUTION_ROOT_DIRECT_OWNER_EXPORTS = True
CANONICAL_OWNER_EXECUTION_SURFACE = "execution"

_OWNER_MAP = {
    'GoalExecutionRequest': ('execution.headless_contract', 'GoalExecutionRequest'),
    'GoalExecutionReport': ('execution.headless_contract', 'GoalExecutionReport'),
    'HeadlessExecutionContract': ('execution.headless_contract', 'HeadlessExecutionContract'),
    'HeadlessRuntime': ('execution.headless_boot', 'HeadlessRuntime'),
    'build_headless_runtime': ('execution.headless_boot', 'build_headless_runtime'),
    'BusinessMemoryCompactor': ('execution.business_operating_memory', 'BusinessMemoryCompactor'),
    'BusinessMemoryPolicy': ('execution.business_operating_memory', 'BusinessMemoryPolicy'),
    'BusinessOperatingMemory': ('execution.business_operating_memory', 'BusinessOperatingMemory'),
    'GovernanceService': ('execution.governance_service', 'GovernanceService'),
    'MemoryAwareRollbackRecommender': ('execution.rollback_recommender', 'MemoryAwareRollbackRecommender'),
    'BusinessMemoryGovernanceGate': ('execution.business_memory_governance', 'BusinessMemoryGovernanceGate'),
    'BusinessMemoryPromotionHelper': ('execution.business_memory_promotion', 'BusinessMemoryPromotionHelper'),
    'canonical_governance_decision': ('execution.canonical_governance_decision', 'canonical_governance_decision'),
    'canonical_governance_evidence': ('execution.canonical_governance_evidence', 'canonical_governance_evidence'),
    'BusinessMemoryMatcher': ('execution.business_memory_matcher', 'BusinessMemoryMatcher'),
    'BusinessMemoryTaxonomy': ('execution.business_memory_taxonomy', 'BusinessMemoryTaxonomy'),
    'BusinessMemoryQueryService': ('execution.business_memory_query', 'BusinessMemoryQueryService'),
    'BusinessMemoryStateAdapter': ('execution.business_memory_state_adapter', 'BusinessMemoryStateAdapter'),
    'RevenueDecisionEnvelope': ('execution.revenue_os_adapter', 'RevenueDecisionEnvelope'),
    'RevenueOSAdapter': ('execution.revenue_os_adapter', 'RevenueOSAdapter'),
}


def _load_attr(module_name: str, attr_name: str) -> Any:
    return getattr(import_module(module_name), attr_name)


# Package-root owner exports are resolved lazily by __getattr__.
# Do not eager-import governance/evidence here: those routes depend on business
# memory evidence projection, and eager loading reintroduces a hidden import cycle.


def __getattr__(name: str) -> Any:
    if name in {
        'CANON_EXECUTION_PACKAGE_OWNER',
        'CANON_EXECUTION_PUBLIC_API',
        'CANON_EXECUTION_PUBLIC_API_COMPAT_SHELL',
        'CANON_EXECUTION_COMPAT_SHIM',
        'CANON_EXECUTION_ROOT_DIRECT_OWNER_EXPORTS',
        'CANONICAL_OWNER_EXECUTION_SURFACE',
    }:
        return globals()[name]
    target = _OWNER_MAP.get(name)
    if target is not None:
        module_name, attr_name = target
        value = _load_attr(module_name, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    'CANON_EXECUTION_PACKAGE_OWNER',
    'CANON_EXECUTION_PUBLIC_API',
    'CANON_EXECUTION_PUBLIC_API_COMPAT_SHELL',
    'CANON_EXECUTION_COMPAT_SHIM',
    'CANON_EXECUTION_ROOT_DIRECT_OWNER_EXPORTS',
    'CANONICAL_OWNER_EXECUTION_SURFACE',
    *_OWNER_MAP.keys(),
]


install_public_api_alias(__name__)
