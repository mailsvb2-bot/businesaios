from __future__ import annotations

from execution.business_memory_policy import BusinessMemoryPolicy
from execution.business_memory_compactor import BusinessMemoryCompactor
from execution.business_memory_store_support import (
    migrate_business_memory_payload as _migrate_business_memory_payload_owner,
    run_record_from_row as _run_record_from_row_owner,
    signal_record_from_row as _signal_record_from_row_owner,
)
from application.memory.business_operating_memory import (
    BusinessOperatingMemory,
    FileBusinessOperatingMemoryStore,
    canonicalize_business_memory_payload as _canonicalize_business_memory_payload,
    project_business_memory_contract_bundle as _project_business_memory_contract_bundle,
    project_business_memory_evidence as _project_business_memory_evidence,
    project_business_memory_feedback_snapshot as _project_business_memory_feedback_snapshot,
    project_business_memory_governance_summary as _project_business_memory_governance_summary,
    project_business_memory_meta_payloads as _project_business_memory_meta_payloads,
    project_business_memory_patterns as _project_business_memory_patterns,
    project_business_memory_profile as _project_business_memory_profile,
    project_business_memory_recent_runs as _project_business_memory_recent_runs,
    project_business_memory_state_context as _project_business_memory_state_context,
    project_business_memory_summary as _project_business_memory_summary,
)

CANON_BUSINESS_OPERATING_MEMORY_COMPAT_SHIM = True
CANON_BUSINESS_OPERATING_MEMORY_FINAL_OWNER = "application.memory.business_operating_memory"


def _migrate_business_memory_payload_owner_bridge(payload, *, policy):
    return _migrate_business_memory_payload_owner(payload, policy=policy)


def _run_record_from_row_owner_bridge(row, *, policy):
    return _run_record_from_row_owner(row, policy=policy)


def _signal_record_from_row_owner_bridge(row, *, policy):
    return _signal_record_from_row_owner(row, policy=policy)


def canonicalize_business_memory_payload(*args, **kwargs):
    return _canonicalize_business_memory_payload(*args, **kwargs)


def project_business_memory_evidence(*args, **kwargs):
    return _project_business_memory_evidence(*args, **kwargs)


def project_business_memory_summary(*args, **kwargs):
    return _project_business_memory_summary(*args, **kwargs)


def project_business_memory_governance_summary(*args, **kwargs):
    return _project_business_memory_governance_summary(*args, **kwargs)


def project_business_memory_patterns(*args, **kwargs):
    return _project_business_memory_patterns(*args, **kwargs)


def project_business_memory_profile(*args, **kwargs):
    return _project_business_memory_profile(*args, **kwargs)


def project_business_memory_recent_runs(*args, **kwargs):
    return _project_business_memory_recent_runs(*args, **kwargs)


def project_business_memory_state_context(*args, **kwargs):
    return _project_business_memory_state_context(*args, **kwargs)


def project_business_memory_feedback_snapshot(*args, **kwargs):
    return _project_business_memory_feedback_snapshot(*args, **kwargs)


def _project_business_memory_contract_bundle_owner(*args, **kwargs):
    return _project_business_memory_contract_bundle(*args, **kwargs)


def project_business_memory_contract_bundle(*args, **kwargs):
    return _project_business_memory_contract_bundle_owner(*args, **kwargs)


def _project_business_memory_meta_payloads_owner(*args, **kwargs):
    return _project_business_memory_meta_payloads(*args, **kwargs)


def project_business_memory_meta_payloads(*args, **kwargs):
    return _project_business_memory_meta_payloads_owner(*args, **kwargs)


__all__ = [
    'BusinessMemoryPolicy',
    'BusinessMemoryCompactor',
    'BusinessOperatingMemory',
    'FileBusinessOperatingMemoryStore',
    'canonicalize_business_memory_payload',
    'project_business_memory_evidence',
    'project_business_memory_summary',
    'project_business_memory_governance_summary',
    'project_business_memory_patterns',
    'project_business_memory_profile',
    'project_business_memory_recent_runs',
    'project_business_memory_state_context',
    'project_business_memory_feedback_snapshot',
    '_project_business_memory_contract_bundle_owner',
    'project_business_memory_contract_bundle',
    '_project_business_memory_meta_payloads_owner',
    'project_business_memory_meta_payloads',
]
