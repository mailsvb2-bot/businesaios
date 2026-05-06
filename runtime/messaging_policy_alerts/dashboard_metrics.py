from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicyDashboardMetrics:
    traces_total: int
    success_rate: float
    all_failed_rate: float
    blocked_trace_rate: float
    attempts_total: int
    selected_channel_counts: tuple[tuple[str, int], ...]
    delivered_channel_counts: tuple[tuple[str, int], ...]
    failed_channel_counts: tuple[tuple[str, int], ...]
    blocked_channel_counts: tuple[tuple[str, int], ...]
    terminal_reason_counts: tuple[tuple[str, int], ...]
