from runtime.business_autonomy.provider_runtime_observability import ProviderRuntimeObservability


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
