from __future__ import annotations

from pathlib import Path

def test_no_routing_outside_decision_path():
    src = Path('routing/demand_router.py').read_text(encoding='utf-8')
    assert 'RoutingDecision(' not in src
    assert '.submit(' not in src
