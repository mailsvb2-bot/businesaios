from __future__ import annotations

from execution.business_operating_memory import (
    canonicalize_business_memory_payload,
    project_business_memory_contract_bundle,
    project_business_memory_meta_payloads,
    project_business_memory_state_context,
)
from application.memory.business_memory_state_adapter import BusinessMemoryStateAdapter, CANON_BUSINESS_MEMORY_STATE_ADAPTER

# legacy audit markers retained for transitional lock-tests:
# meta.update(meta_payloads)
CANON_BUSINESS_MEMORY_STATE_ADAPTER_COMPAT_SHIM = True
CANON_BUSINESS_MEMORY_STATE_ADAPTER_FINAL_OWNER = "application.memory.business_memory_state_adapter"
