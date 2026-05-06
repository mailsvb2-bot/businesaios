from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MessagingPolicyAccumulator:
    tenant_id: str
    user_id: str
    correlation_id: str
    delivered: list[str]
    failed: list[str]
    blocked: list[str]
    last_plan_channels: tuple[str, ...]
    last_selected_channel: str
    last_terminal_reason: str
    attempts_count: int
