from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_no_hardcoded_email_channel_in_dispatcher() -> None:
    source = (ROOT / 'routing_execution' / 'lead_delivery_dispatcher.py').read_text(encoding='utf-8')
    assert 'channel = "email"' not in source
    assert 'ChannelSelector' in source
