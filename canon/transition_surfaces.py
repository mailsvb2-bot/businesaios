"""Canonical registry for transition-only import surfaces.

These modules exist only to preserve stable imports during controlled
architecture collapse. Thin package-alias namespaces are preferred over
standalone shim files whenever the import ABI can stay stable without a second
physical surface. Package-owned ``*/public_api.py`` modules remain the only
retained public-api compatibility surface; repo-root dotted pseudo-files are
retired.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

CANON_TRANSITION_SURFACE: Final[bool] = True
TRANSITION_SURFACE_MARKER: Final[str] = "CANON_TRANSITION_SURFACE = True"
COMPAT_SHIM_MARKER: Final[str] = "CANON_COMPAT_SHIM = True"

TRANSITION_SURFACE_MODULES: Final[tuple[str, ...]] = (
    "core/decision/__init__.py",
    "core/products/__init__.py",
    "demand_guardrails/customer_fit_guard.py",
    "demand_guardrails/demand_decision_guard.py",
    "demand_guardrails/fraud_pattern_guard.py",
    "demand_guardrails/no_monopoly_guard.py",
    "demand_guardrails/rollback_guard.py",
    "demand_guardrails/routing_risk_guard.py",
)

TRANSITION_PACKAGE_ALIAS_MODULES: Final[dict[str, str]] = {
    "runtime.read_only_registry": "runtime.application",
    "runtime.service_exports": "runtime.application",
    "runtime.capability_access": "runtime.application",
    "runtime.typed_access": "runtime.application",
    "runtime.domain_ports": "runtime.application",
    "runtime.executor_contract": "runtime.execution.contracts",
    "runtime.ai_ceo.public_api": "runtime.ai_ceo",
    "runtime.behavior.public_api": "runtime.behavior",
    "runtime.decision": "runtime.decision",
    "runtime.economics": "runtime.economics",
    "runtime.enforcement.public_api": "runtime.enforcement",
    "runtime.events": "runtime.events",
    "runtime.execution.public_api": "runtime.execution",
    "runtime.experiments.public_api": "runtime.experiments",
    "runtime.explainability.public_api": "runtime.explainability",
    "runtime.finance.public_api": "runtime.finance",
    "runtime.growth.public_api": "runtime.growth",
    "runtime.human_governance.public_api": "runtime.human_governance",
    "runtime.knowledge.public_api": "runtime.knowledge",
    "runtime.learning_loop.public_api": "runtime.learning_loop",
    "runtime.product.public_api": "runtime.product",
    "runtime.proofs": "runtime.proofs",
    "runtime.proofs.public_api": "runtime.proofs",
    "runtime.ratelimit.public_api": "runtime.ratelimit",
    "runtime.safety.public_api": "runtime.safety",
    "runtime.simulation.public_api": "runtime.simulation",
    "runtime.state.public_api": "runtime.state",
    "runtime.tenancy.public_api": "runtime.tenancy",
    "runtime.world_model.public_api": "runtime.world_model",
    "runtime.world_state.public_api": "runtime.world_state",
    "observability.platform.observability.public_api": "observability.platform.observability",
    "observability.platform.public_api": "observability.platform",
    "observability.public_api": "observability",
    "acquisition.public_api": "acquisition",
}

TRANSITION_CANONICAL_TARGETS: Final[dict[str, str]] = {
    "demand_guardrails/customer_fit_guard.py": "guardrails/demand_policies.py",
    "demand_guardrails/demand_decision_guard.py": "guardrails/demand_policies.py",
    "demand_guardrails/fraud_pattern_guard.py": "guardrails/demand_policies.py",
    "demand_guardrails/no_monopoly_guard.py": "guardrails/demand_policies.py",
    "demand_guardrails/rollback_guard.py": "guardrails/demand_policies.py",
    "demand_guardrails/routing_risk_guard.py": "guardrails/demand_policies.py",
}


def is_transition_surface_path(path: str | Path) -> bool:
    normalized = Path(path).as_posix().lstrip("./")
    return normalized in TRANSITION_SURFACE_MODULES


__all__ = [
    "CANON_TRANSITION_SURFACE",
    "COMPAT_SHIM_MARKER",
    "TRANSITION_SURFACE_MARKER",
    "TRANSITION_SURFACE_MODULES",
    "TRANSITION_CANONICAL_TARGETS",
    "TRANSITION_PACKAGE_ALIAS_MODULES",
    "is_transition_surface_path",
]
