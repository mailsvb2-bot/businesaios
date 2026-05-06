from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'runtime/business_autonomy/provider_webhook_inbound_handoff.py'


def test_provider_webhook_inbound_handoff_is_single_owner_for_canonical_handoff_mapping():
    text = TARGET.read_text(encoding='utf-8')
    assert 'build_provider_webhook_inbound_handoff' in text
    assert 'InboundMessage(' in text
    assert 'map_inbound_to_world_state' in text

    offenders = []
    for path in (ROOT / 'runtime').rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if rel == 'runtime/business_autonomy/provider_webhook_inbound_handoff.py':
            continue
        src = path.read_text(encoding='utf-8')
        if 'ingress_owner\': \'runtime.messaging.inbound_entrypoint\'' in src or 'ingress_owner": "runtime.messaging.inbound_entrypoint"' in src:
            offenders.append(rel)
    assert not offenders, offenders
