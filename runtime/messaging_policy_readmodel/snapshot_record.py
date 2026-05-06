from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicySnapshotRecord:
    tenant_id: str
    user_id: str
    correlation_id: str
    delivered: tuple[str, ...]
    failed: tuple[str, ...]
    blocked: tuple[str, ...]
    last_plan_channels: tuple[str, ...]
    last_selected_channel: str
    last_terminal_reason: str
    attempts_count: int
