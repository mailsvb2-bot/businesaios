from __future__ import annotations

from dataclasses import dataclass

from runtime.messaging_capability.capability_requirement import CapabilityRequirement


@dataclass(frozen=True)
class MessagingCapabilityRouteRequest:
    ordered_channels: tuple[str, ...]
    requirement: CapabilityRequirement
