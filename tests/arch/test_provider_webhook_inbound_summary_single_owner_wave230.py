from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'runtime/business_autonomy/provider_webhook_inbound_result_summary.py'


def test_provider_webhook_inbound_summary_is_single_owner():
    text = TARGET.read_text(encoding='utf-8')
    assert 'summarize_provider_webhook_inbound_result' in text

    offenders = []
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if rel == 'runtime/business_autonomy/provider_webhook_inbound_result_summary.py' or rel.startswith('tests/'):
            continue
        src = path.read_text(encoding='utf-8')
        if 'decision_id' in src and 'transport_message_id' in src and 'messaging_inbound_summary' in src:
            offenders.append(rel)
    assert not offenders, offenders
