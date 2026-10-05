from __future__ import annotations

from application.memory.business_memory_compactor import BusinessMemoryCompactor
from application.memory.business_memory_policy import BusinessMemoryPolicy
from application.memory.business_operating_memory import (
    MEMORY_LIFECYCLE,
    BusinessOperatingMemory,
    FileBusinessOperatingMemoryStore,
    add_memory_candidate,
    canonicalize_business_memory_payload,
    project_business_memory_contract_bundle,
    project_business_memory_contract_bundle as _project_business_memory_contract_bundle_owner,
    project_business_memory_evidence,
    project_business_memory_feedback_snapshot,
    persist_memory_candidate,
    persist_memory_transition,
    project_business_memory_governance_summary,
    project_business_memory_v2,
    project_business_memory_meta_payloads,
    project_business_memory_meta_payloads as _project_business_memory_meta_payloads_owner,
    project_business_memory_patterns,
    project_business_memory_profile,
    project_business_memory_recent_runs,
    project_business_memory_state_context,
    project_business_memory_summary,
    project_memory_knowledge_graph,
    project_portable_memory,
    transition_memory,
)
from execution.business_memory_store_support import (
    migrate_business_memory_payload as _migrate_business_memory_payload_owner_bridge,
    run_record_from_row as _run_record_from_row_owner_bridge,
    signal_record_from_row as _signal_record_from_row_owner_bridge,
)

CANON_BUSINESS_OPERATING_MEMORY_COMPAT_SHIM = True
CANON_BUSINESS_OPERATING_MEMORY_FINAL_OWNER = "application.memory.business_operating_memory"

__all__ = [
    "BusinessMemoryPolicy", "BusinessMemoryCompactor", "MEMORY_LIFECYCLE", "BusinessOperatingMemory",
    "FileBusinessOperatingMemoryStore", "add_memory_candidate", "canonicalize_business_memory_payload",
    "project_business_memory_evidence", "project_business_memory_summary", "persist_memory_candidate",
    "persist_memory_transition", "project_business_memory_governance_summary", "project_business_memory_v2",
    "project_business_memory_patterns", "project_business_memory_profile", "project_business_memory_recent_runs",
    "project_business_memory_state_context", "project_business_memory_feedback_snapshot",
    "_project_business_memory_contract_bundle_owner", "project_business_memory_contract_bundle",
    "_project_business_memory_meta_payloads_owner", "project_business_memory_meta_payloads",
    "project_memory_knowledge_graph", "project_portable_memory", "transition_memory",
]
