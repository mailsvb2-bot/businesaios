from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inbound_owner_lock_has_explicit_allowed_entrypoints():
    text = (ROOT / 'runtime/messaging/inbound_owner_lock.py').read_text(encoding='utf-8')
    required = (
        "runtime.messaging.inbound_entrypoint",
        "runtime.business_autonomy.provider_webhook_inbound_processor",
    )
    missing = [item for item in required if item not in text]
    assert not missing, missing


def test_no_direct_issue_locked_decision_inside_messaging_ingress_surfaces():
    offenders = []
    target_roots = [ROOT / 'interfaces', ROOT / 'runtime/messaging']
    for base in target_roots:
        for path in base.rglob('*.py'):
            rel = path.relative_to(ROOT).as_posix()
            if rel == 'runtime/messaging/inbound_entrypoint.py':
                continue
            text = path.read_text(encoding='utf-8')
            if 'issue_locked_decision(' in text:
                offenders.append(rel)
    assert not offenders, offenders


def test_telegram_handler_uses_canonical_inbound_entrypoint():
    text = (ROOT / 'interfaces/telegram/telegram_handler.py').read_text(encoding='utf-8')
    assert 'handle_inbound_message(' in text
