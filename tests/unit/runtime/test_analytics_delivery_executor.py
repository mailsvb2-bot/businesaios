from __future__ import annotations

from runtime._internal.effects_domains.analytics_delivery_executor import execute_analytics_webhook_delivery


def test_analytics_delivery_executor_uses_transport(monkeypatch):
    def fake_sync_post_json(*, url, headers, data, timeout_s):
        class _Resp:
            status = 202
            json = {'accepted': True}
            text = 'ok'
        return _Resp()

    monkeypatch.setattr('runtime._internal.effects_domains.analytics_delivery_executor.sync_post_json', fake_sync_post_json)
    result = execute_analytics_webhook_delivery(
        tenant_id='tenant-1',
        webhook_url='https://example.com/hook',
        payload={'a': 1},
    )
    assert result['ok'] is True
    assert result['status'] == 202
