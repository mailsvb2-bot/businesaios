from __future__ import annotations

from pathlib import Path


def test_match_scorers_do_not_route():
    for path in Path('matching/scorers').glob('*.py'):
        src = path.read_text(encoding='utf-8')
        assert 'RoutingDecision(' not in src
        assert 'selected_business_id' not in src
