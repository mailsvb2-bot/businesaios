from __future__ import annotations

import importlib

_COMPAT_TARGETS = {
    "core.decision.decision_candidate": "core.contracts.decision_candidate",
    "core.decision.decision_context": "core.contracts.decision_context",
    "core.decision.decision_reason": "core.contracts.decision_reason",
    "core.decision.decision_rejection": "core.contracts.decision_rejection",
    "core.decision.decision_request": "core.contracts.decision_request",
    "core.decision.decision_result": "core.contracts.decision_result",
    "core.decision.decision_space": "core.contracts.decision_space",
    "core.decision.decision_trace": "core.contracts.decision_trace",
    "core.decision.decision_history": "core.policy.decision_history",
    "core.decision.decision_publisher": "core.policy.decision_publisher",
    "core.decision.decision_space_narrowing_audit": "core.policy.decision_space_narrowing_audit",
    "core.decision.decision_validator": "core.policy.decision_validator",
}


def test_core_decision_compat_modules_resolve_to_single_owner_modules() -> None:
    for alias_name, owner in _COMPAT_TARGETS.items():
        alias_module = importlib.import_module(alias_name)
        owner_module = importlib.import_module(owner)
        assert alias_module is owner_module, alias_name
