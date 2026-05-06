from __future__ import annotations

from pathlib import Path

CRITICAL_FILES = [
    Path("runtime/handlers/ai_ceo_plan.py"),
    Path("runtime/handlers/ads_autopilot_tick.py"),
    Path("runtime/handlers/ads_autopilot/result_format.py"),
    Path("runtime/handlers/ads_autopilot_tick_parts/request_factory.py"),
    Path("runtime/handlers/ads_autopilot_tick_parts/runner.py"),
]


def test_lock_no_inline_bootstrap_snippets_left_in_critical_handlers() -> None:
    forbidden = ("sys.path.insert", "ModuleType(", "standalone file import support")
    for rel in CRITICAL_FILES:
        text = rel.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{rel} still contains inline bootstrap marker: {marker}"
