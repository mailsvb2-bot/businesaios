from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingCapabilityRouteResult:
    ordered_channels: tuple[str, ...]
    reason_codes: tuple[str, ...]
