from __future__ import annotations

from pathlib import Path


def test_supply_state_feeds_do_not_emit_decisions():
    for path in Path('supply_state/feeds').glob('*.py'):
        src = path.read_text(encoding='utf-8')
        assert 'RoutingDecision(' not in src
        assert '.submit(' not in src
