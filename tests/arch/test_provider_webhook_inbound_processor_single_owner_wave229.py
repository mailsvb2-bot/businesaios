from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'runtime/business_autonomy/provider_webhook_inbound_processor.py'


def test_provider_webhook_inbound_processor_is_single_owner_for_runtime_handoff_execution():
    text = TARGET.read_text(encoding='utf-8')
    assert 'ProviderWebhookInboundProcessor' in text
    assert 'MessagingInboundDecisionGateway' in text
    assert "runtime.business_autonomy.provider_webhook_inbound_processor" in text

    offenders = []
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if rel == 'runtime/business_autonomy/provider_webhook_inbound_processor.py' or rel.startswith('tests/'):
            continue
        src = path.read_text(encoding='utf-8')
        if "runtime.business_autonomy.provider_webhook_inbound_processor" in src and 'caller=' in src:
            offenders.append(rel)
    assert not offenders, offenders
