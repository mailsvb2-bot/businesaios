from __future__ import annotations

from typing import Any

from runtime.handlers.ads_autopilot.result_snapshot import snapshot_autopilot_result
from runtime.handlers.ads_autopilot.result_text import (
    render_autopilot_result_text,
    render_gate_error_text,
)


def format_autopilot_result(res: Any) -> str:
    try:
        return render_autopilot_result_text(snapshot_autopilot_result(res))
    except (AttributeError, TypeError, ValueError):
        return '🤖 Ads Autopilot: done'


def gate_error_text(exc: Exception) -> str:
    return render_gate_error_text(exc)
