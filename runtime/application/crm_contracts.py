from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeCrmContracts:
    service_name: str = 'crm_service'
    world_state_enricher: str = 'crm_world_state_enricher'
    memory_adapter: str = 'crm_memory_adapter'
