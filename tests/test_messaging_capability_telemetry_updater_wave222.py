from runtime.messaging_capability.channel_health import ChannelHealth
from runtime.messaging_capability.channel_health_registry import ChannelHealthRegistry
from runtime.messaging_capability.telemetry_updater import MessagingCapabilityTelemetryUpdater


def test_noop_outcome_does_not_degrade_health():
    registry = ChannelHealthRegistry(items=(ChannelHealth(channel="email", healthy=True, health_score=0.9, reason="ok"),))
    updater = MessagingCapabilityTelemetryUpdater(registry=registry)
    out = updater.record_delivery_outcome(channel="email", ok=False, meta={"mode": "configured_noop", "reason": "provider_not_enabled"})
    assert out.health_score == 0.9
    assert out.reason == "ok"


def test_blocked_failure_degrades_health():
    registry = ChannelHealthRegistry(items=(ChannelHealth(channel="sms", healthy=True, health_score=0.9, reason="ok"),))
    updater = MessagingCapabilityTelemetryUpdater(registry=registry)
    out = updater.record_delivery_outcome(channel="sms", ok=False, meta={"mode": "webhook", "reason": "blocked"})
    assert out.health_score < 0.9
    assert out.reason == "blocked"
