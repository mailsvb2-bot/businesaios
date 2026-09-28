from runtime.business_autonomy.provider_runtime_observability import ProviderRuntimeObservability


class _Registry:
    def __init__(self):
        self.inc_calls = []
        self.rate_calls = []
        self.error_calls = []
        self.latency_calls = []

    def inc(self, **kwargs):
        self.inc_calls.append(kwargs)

    def record_success_rate(self, **kwargs):
        self.rate_calls.append(kwargs)

    def record_error_rate(self, **kwargs):
        self.error_calls.append(kwargs)

    def observe_latency_ms(self, **kwargs):
        self.latency_calls.append(kwargs)

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


def test_record_sync_emits_provider_scoped_error_and_latency_metrics():
    reg = _Registry()
    obs = ProviderRuntimeObservability(metrics_registry=reg)
    obs.record_sync(tenant_id='t1', provider_key='telegram_bot', operation='message_send', status='live_executed', accepted=True, mode='live', latency_ms=125.0)
    assert reg.rate_calls[-1]['labels'] == {'provider_key': 'telegram_bot', 'mode': 'live'}
    assert reg.error_calls[-1]['error_ratio'] == 0.0
    assert reg.latency_calls[-1]['value_ms'] == 125.0


def test_provider_truth_is_label_filtered_by_provider_and_mode():
    obs = ProviderRuntimeObservability()
    obs.record_sync(tenant_id='t1', provider_key='telegram_bot', operation='message_send', status='ok', accepted=True, mode='live', latency_ms=100.0)
    obs.record_sync(tenant_id='t1', provider_key='telegram_bot', operation='message_send', status='failed', accepted=False, mode='live', latency_ms=300.0)
    obs.record_sync(tenant_id='t1', provider_key='whatsapp_cloud', operation='message_send', status='ok', accepted=True, mode='live', latency_ms=900.0)
    obs.record_sync(tenant_id='t1', provider_key='telegram_bot', operation='message_send', status='dry', accepted=True, mode='dry_run', latency_ms=1.0)
    truth = obs.provider_truth(tenant_id='t1', provider_key='telegram_bot')
    assert truth['reliability'] == 0.5
    assert truth['error_rate'] == 0.5
    assert truth['latency_ms'] == 300.0
    assert truth['sample_count'] == 2
