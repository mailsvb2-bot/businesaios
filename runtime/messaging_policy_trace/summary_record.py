from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicyTraceSummary:
    tenant_id: str
    user_id: str
    correlation_id: str
    decision_id: str
    created_at: str
    updated_at: str
    attempts_count: int
    selected_channel: str
    terminal_reason: str
    delivered: tuple[str, ...]
    failed: tuple[str, ...]
    blocked: tuple[str, ...]
    last_plan_channels: tuple[str, ...]
