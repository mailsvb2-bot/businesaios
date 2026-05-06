from __future__ import annotations

from registry.base_registry import BaseRegistry

class LeadDeliveryRegistry(BaseRegistry):
    def __init__(self) -> None:
        super().__init__(kind="channel_adapter")
