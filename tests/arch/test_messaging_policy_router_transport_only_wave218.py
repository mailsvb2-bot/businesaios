from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'runtime/messaging/router.py'

def test_router_is_transport_normalizer_only() -> None:
    text = TARGET.read_text(encoding='utf-8')
    forbidden=('DecisionCore','resolve_strategy','ranker','llm','optimize(','world_model','reward')
    offenders=[item for item in forbidden if item in text]
    assert not offenders, offenders
