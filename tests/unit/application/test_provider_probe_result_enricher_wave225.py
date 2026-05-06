from application.business_autonomy.provider_runtime_contract import ProviderLiveProbeResult
from runtime.business_autonomy.provider_probe_result_enricher import enrich_probe_result_with_messaging_health
from runtime.messaging_capability.channel_health_registry import ChannelHealthRegistry


class _Provider:
    provider_key = "telegram_bot"
    messaging_channel = "telegram"
    messaging_capabilities = {"plain_text": True}
    messaging_live_probe_supported = True


def test_enrich_probe_result_with_messaging_health_attaches_metadata_and_updates_registry():
    registry = ChannelHealthRegistry()
    result = ProviderLiveProbeResult(
        provider_key="telegram_bot",
        mode="live",
        status="probe_live_failed",
        ok=False,
        metadata={},
    )
    out = enrich_probe_result_with_messaging_health(
        registry=registry,
        provider=_Provider(),
        probe_result=result,
    )
    signal = dict(out.metadata.get("messaging_health_signal") or {})
    assert signal.get("channel") == "telegram"
    assert signal.get("measurable") is True
    assert registry.get("telegram").healthy is False
