from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicySnapshotState:
    delivered: tuple[str, ...]
    failed: tuple[str, ...]
    blocked: tuple[str, ...]
    last_plan_channels: tuple[str, ...]
    last_selected_channel: str
    last_terminal_reason: str
    attempts_count: int
