from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicyDashboardResult:
    traces_total: int
    traces_with_success: int
    traces_all_failed: int
    traces_with_blocked: int
    attempts_total: int
    success_rate: float
    all_failed_rate: float
    blocked_trace_rate: float
    selected_channel_counts: tuple[tuple[str, int], ...]
    delivered_channel_counts: tuple[tuple[str, int], ...]
    failed_channel_counts: tuple[tuple[str, int], ...]
    blocked_channel_counts: tuple[tuple[str, int], ...]
    terminal_reason_counts: tuple[tuple[str, int], ...]
