"""Compatibility facade for the single canonical governance runtime.

This module historically contained a second implementation of execution
governance.  That duplicate drifted from :mod:`governance_runtime` and even
used a conflicting approval-resolution contract.  It now exposes only direct
aliases to the canonical runtime plus the audit-only helper module.
"""

from __future__ import annotations

from runtime.execution.governance_audit_support import (
    _append_governance_audit,
    _governance_audit_log,
)
from runtime.execution.governance_runtime import (
    CANON_RUNTIME_GOVERNANCE_EXECUTION_GATE,
    GovernanceExecutionBlocked,
    _apply_approval_workflow_resolution,
    _approval_gate_enabled,
    _build_actor,
    _build_approval_output,
    _build_default_approval_execution_gate,
    _build_impact,
    _build_resume_governance_hint,
    _consume_operator_override,
    _emit_resume_event,
    _execution_approval_gate,
    _execution_operator_override_store,
    _extract_approval_id,
    _extract_operator_override_id,
    _gate_metadata,
    _infer_category,
    _load_operator_override,
    _materialize_operator_override_approval,
    _normalize_non_negative_int,
    _normalize_roles,
    _safe_dict,
    _should_enforce,
    review_governance_execution,
)

__all__ = [
    "CANON_RUNTIME_GOVERNANCE_EXECUTION_GATE",
    "GovernanceExecutionBlocked",
    "_append_governance_audit",
    "_governance_audit_log",
    "_apply_approval_workflow_resolution",
    "_approval_gate_enabled",
    "_build_actor",
    "_build_approval_output",
    "_build_default_approval_execution_gate",
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
]
