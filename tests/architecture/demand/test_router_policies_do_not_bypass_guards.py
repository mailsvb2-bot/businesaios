from __future__ import annotations

from pathlib import Path

def test_router_policies_do_not_bypass_guards():
    for path in Path('routing/policies').glob('*.py'):
        src = path.read_text(encoding='utf-8')
        assert '.deliver(' not in src
        assert 'RoutingDecision(' not in src
