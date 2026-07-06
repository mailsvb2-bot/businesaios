"""Compatibility package for decision contracts.

Canonical owners now live in ``kernel.*``. This package remains as a stable
transition surface for legacy imports.
"""

from __future__ import annotations

import sys
from importlib import import_module

from kernel.decision_candidate import DecisionCandidate
from kernel.decision_context import DecisionContext
from kernel.decision_reason import DecisionReason
from kernel.decision_rejection import DecisionRejection
from kernel.decision_request import DecisionRequest
from kernel.decision_result import DecisionResult
from kernel.decision_space import DecisionSpace
from kernel.decision_trace import DecisionTrace

__all__ = [
    'DecisionCandidate', 'DecisionContext', 'DecisionRequest', 'DecisionResult',
    'DecisionReason', 'DecisionRejection', 'DecisionTrace', 'DecisionSpace',
]
_COMPAT_ALIAS_MAP = {
    "product_contract": "contracts.product_contract",
}

def _install_contract_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target_module_name in _COMPAT_ALIAS_MAP.items():
        target_module = import_module(target_module_name)
        qualified_name = f"{__name__}.{alias_name}"
        sys.modules[qualified_name] = target_module
        setattr(package, alias_name, target_module)


_install_contract_aliases()
