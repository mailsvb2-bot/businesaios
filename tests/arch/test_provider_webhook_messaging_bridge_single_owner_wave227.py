from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'runtime/business_autonomy/provider_webhook_messaging_bridge.py'


def test_provider_webhook_messaging_bridge_is_single_owner_for_ingress_mapping() -> None:
    text = TARGET.read_text(encoding='utf-8')
    assert 'resolve_provider_webhook_messaging_ingress' in text
    assert 'messaging_ingress_to_metadata' in text

    offenders = []
    for path in (ROOT / 'runtime/business_autonomy').rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if rel == 'runtime/business_autonomy/provider_webhook_messaging_bridge.py':
            continue
        src = path.read_text(encoding='utf-8')
        if 'ProviderWebhookMessagingIngress(' in src:
            offenders.append(rel)
    assert not offenders, offenders
