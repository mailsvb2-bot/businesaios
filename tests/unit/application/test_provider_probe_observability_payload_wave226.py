from runtime.business_autonomy.provider_probe_observability_payload import (
    build_live_probe_gauge_payload,
    build_live_probe_labels,
)


def test_build_live_probe_labels_includes_messaging_signal_dimensions():
    labels = build_live_probe_labels(
        provider_key='telegram_bot',
        status='probe_live_failed',
        mode='live',
        metadata={
            'messaging_health_signal': {
                'channel': 'telegram',
                'measurable': True,
                'healthy': False,
                'health_score': 0.0,
                'reason': 'probe_live_failed',
            }
        },
    )
    assert labels['messaging_channel'] == 'telegram'
    assert labels['messaging_healthy'] == 'false'
    assert labels['messaging_reason'] == 'probe_live_failed'


def test_build_live_probe_gauge_payload_only_for_measurable_signal():
    assert build_live_probe_gauge_payload(metadata={}) is None
    assert build_live_probe_gauge_payload(metadata={'messaging_health_signal': {'measurable': False, 'health_score': 1.0}}) is None
    out = build_live_probe_gauge_payload(metadata={'messaging_health_signal': {'measurable': True, 'health_score': 0.5}})
    assert out == ('provider_runtime.messaging_health_score', 0.5)
