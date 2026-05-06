from __future__ import annotations


def update_kpis(*, state, summary) -> None:
    state.traces_total += 1
    state.attempts_total += int(summary.attempts_count)

    if tuple(summary.delivered):
        state.traces_with_success += 1

    if str(summary.terminal_reason or '') == 'all_attempts_failed':
        state.traces_all_failed += 1

    if tuple(summary.blocked):
        state.traces_with_blocked += 1
