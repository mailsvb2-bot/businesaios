from __future__ import annotations

from pathlib import Path


def test_no_hidden_match_winner_selection():
    src = Path('matching/match_engine.py').read_text(encoding='utf-8')
    assert 'selected_business_id' not in src
    assert 'RoutingDecision(' not in src
