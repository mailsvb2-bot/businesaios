from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from crm.crm_capability_contract import CrmCapabilityDescriptor


@dataclass(frozen=True)
class CrmProvider:
    provider_key: str
    display_name: str
    capability_descriptor: CrmCapabilityDescriptor
    enabled: bool = True
    default_rank: int = 100
    metadata: Mapping[str, object] = field(default_factory=dict)
