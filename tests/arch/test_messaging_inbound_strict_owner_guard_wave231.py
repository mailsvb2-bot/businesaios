from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inbound_strict_owner_guard_allows_only_canonical_owners():
    text = (ROOT / 'runtime/messaging/inbound_strict_owner_guard.py').read_text(encoding='utf-8')
    assert 'runtime.messaging.inbound_entrypoint' in text
    assert 'runtime.business_autonomy.provider_webhook_inbound_processor' in text
    assert 'interfaces.telegram.telegram_handler' not in text
    assert 'interfaces.web.chat_widget.api_handlers' not in text


def test_telegram_handler_uses_entrypoint_not_gateway():
    text = (ROOT / 'interfaces/telegram/telegram_handler.py').read_text(encoding='utf-8')
    assert 'handle_inbound_message(' in text
    assert 'MessagingInboundDecisionGateway' not in text


def test_no_direct_gateway_calls_outside_canonical_owner_paths():
    offenders = []
    allowed = {
        'runtime/business_autonomy/provider_webhook_inbound_processor.py',
        'runtime/messaging/inbound_decision_gateway.py',
    }
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith('tests/'):
            continue
        text = path.read_text(encoding='utf-8')
        if 'MessagingInboundDecisionGateway(' in text and rel not in allowed:
            offenders.append(rel)
    assert not offenders, offenders
