"""Compatibility facade for the single canonical governance runtime."""
from __future__ import annotations

from runtime.execution import governance_runtime as _runtime
from runtime.execution.governance_audit_support import _append_governance_audit, _governance_audit_log

_NAMES = (
    "CANON_RUNTIME_GOVERNANCE_EXECUTION_GATE",
    "GovernanceExecutionBlocked",
    "_apply_approval_workflow_resolution",
    "_approval_gate_enabled",
    "_build_actor",
    "_build_approval_output",
    "_build_impact",
    "_build_resume_governance_hint",
    "_consume_operator_override",
    "_emit_resume_event",
    "_execution_approval_gate",
    "_execution_operator_override_store",
    "_extract_approval_id",
    "_extract_operator_override_id",
    "_gate_metadata",
    "_infer_category",
    "_load_operator_override",
    "_materialize_operator_override_approval",
    "_normalize_non_negative_int",
    "_normalize_roles",
    "_safe_dict",
    "_should_enforce",
    "review_governance_execution",
)
globals().update({name: getattr(_runtime, name) for name in _NAMES})

_build_default_approval_execution_gate = _runtime._build_default_approval_execution_gate
build_default_approval_execution_gate = _build_default_approval_execution_gate
__all__ = [*_NAMES, "_append_governance_audit", "_governance_audit_log", "_build_default_approval_execution_gate", "build_default_approval_execution_gate"]
