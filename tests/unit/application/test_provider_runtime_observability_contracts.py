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


def test_record_live_probe_emits_enriched_labels_and_health_gauge():
    obs = ProviderRuntimeObservability()
    obs.record_live_probe(
        tenant_id='t1',
        provider_key='telegram_bot',
        status='probe_live_ok',
        ok=True,
        mode='live',
        metadata={
            'messaging_health_signal': {
                'channel': 'telegram',
                'measurable': True,
                'healthy': True,
                'health_score': 1.0,
                'reason': 'provider_live_probe_ok',
            }
        },
    )

    snap = obs.metrics_registry.metric_snapshot(tenant_id='t1', metric_name='provider_runtime.live_probe_total')
    assert snap is not None
    assert snap['labels']['messaging_channel'] == 'telegram'
    assert snap['labels']['messaging_measurable'] == 'true'

    gauge = obs.metrics_registry.metric_snapshot(tenant_id='t1', metric_name='provider_runtime.messaging_health_score')
    assert gauge is not None
    assert float(gauge['value']) == 1.0
