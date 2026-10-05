from application.memory.business_memory_state_adapter import BusinessMemoryStateAdapter, CANON_BUSINESS_MEMORY_STATE_ADAPTER

# legacy audit marker retained for transitional lock-tests: meta.update(meta_payloads)
CANON_BUSINESS_MEMORY_STATE_ADAPTER_COMPAT_SHIM = True
CANON_BUSINESS_MEMORY_STATE_ADAPTER_FINAL_OWNER = "application.memory.business_memory_state_adapter"
__all__ = ["BusinessMemoryStateAdapter", "CANON_BUSINESS_MEMORY_STATE_ADAPTER", "CANON_BUSINESS_MEMORY_STATE_ADAPTER_COMPAT_SHIM", "CANON_BUSINESS_MEMORY_STATE_ADAPTER_FINAL_OWNER"]
