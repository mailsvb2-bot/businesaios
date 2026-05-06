from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    ROOT / 'interfaces' / 'web' / 'debug' / 'messaging_policy_snapshot' / 'route_bundle.py',
    ROOT / 'interfaces' / 'web' / 'debug' / 'messaging_policy_trace_search' / 'route_bundle.py',
    ROOT / 'interfaces' / 'web' / 'debug' / 'messaging_policy_dashboard' / 'route_bundle.py',
    ROOT / 'interfaces' / 'web' / 'debug' / 'messaging_policy_alerts' / 'route_bundle.py',
]


def test_debug_query_parsers_use_shared_cleaning_utils() -> None:
    for path in TARGETS:
        src = path.read_text(encoding='utf-8')
        assert 'interfaces.web.debug.common.query_utils' in src
        assert 'def _clean' not in src
