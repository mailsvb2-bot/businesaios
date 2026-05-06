from runtime.business_autonomy.provider_runtime_observability import ProviderRuntimeObservability


class _Registry:
    def __init__(self):
        self.inc_calls = []
        self.rate_calls = []

    def inc(self, **kwargs):
        self.inc_calls.append(kwargs)

    def record_success_rate(self, **kwargs):
        self.rate_calls.append(kwargs)

    def set_gauge(self, **kwargs):
        raise AssertionError('unexpected gauge')


def test_record_webhook_inbound_handoff_emits_canonical_metrics():
    reg = _Registry()
    obs = ProviderRuntimeObservability(metrics_registry=reg)

    obs.record_webhook_inbound_handoff(
        tenant_id='t1',
        provider_key='telegram_bot',
        status='accepted',
        inbound_summary={'accepted': True, 'channel': 'telegram'},
    )

    assert reg.inc_calls[0]['metric_name'] == 'provider_runtime.webhook_inbound_handoff_total'
    assert reg.inc_calls[0]['labels']['channel'] == 'telegram'
    assert reg.rate_calls[0]['metric_name'] == 'provider_runtime.webhook_inbound_handoff_accept_rate'
