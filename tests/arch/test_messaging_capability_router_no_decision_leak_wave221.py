from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'runtime/messaging_capability/router.py'


def test_capability_router_stays_transport_only():
    text = TARGET.read_text(encoding='utf-8')
    forbidden = (
        'DecisionCore',
        'optimize(',
        'resolve_strategy',
        'world_model',
        'send_marketing_offer',
        'pricing',
    )
    offenders = [item for item in forbidden if item in text]
    assert not offenders, offenders
