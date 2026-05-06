from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    ROOT / 'interfaces' / 'web' / 'debug' / 'messaging_policy_snapshot' / 'http_response.py',
    ROOT / 'interfaces' / 'web' / 'debug' / 'messaging_policy_trace_search' / 'http_response.py',
    ROOT / 'interfaces' / 'web' / 'debug' / 'messaging_policy_dashboard' / 'http_response.py',
    ROOT / 'interfaces' / 'web' / 'debug' / 'messaging_policy_alerts' / 'http_response.py',
]


def test_debug_http_response_modules_are_shared_shims() -> None:
    for path in TARGETS:
        src = path.read_text(encoding='utf-8')
        assert 'from interfaces.web.debug.common.http_response import HttpResponse' in src
        assert '@dataclass' not in src
