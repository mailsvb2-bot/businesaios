from runtime.messaging_capability.channel_health_registry import ChannelHealthRegistry
from runtime.messaging_capability.telemetry_updater import MessagingCapabilityTelemetryUpdater


def test_health_feedback_marks_channel_degraded_after_failure():
    registry = ChannelHealthRegistry()
    updater = MessagingCapabilityTelemetryUpdater(registry=registry)
    updated = updater.record_delivery_outcome(channel='telegram', ok=False, meta={'reason': 'timeout'})
    assert updated.channel == 'telegram'
    assert updated.health_score < 1.0
    assert updated.reason == 'timeout'


def test_health_feedback_marks_channel_unhealthy_when_blocked():
    registry = ChannelHealthRegistry()
    updater = MessagingCapabilityTelemetryUpdater(registry=registry)
    updated = updater.record_delivery_outcome(channel='sms', ok=False, meta={'reason': 'blocked'})
    assert updated.healthy is False
    assert updated.health_score <= 0.2
