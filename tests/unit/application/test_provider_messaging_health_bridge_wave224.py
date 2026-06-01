from application.business_autonomy.channel_contracts import ChannelKind
from application.business_autonomy.provider_admin_contract import ProviderDefinition
from runtime.business_autonomy.provider_messaging_health_bridge import resolve_provider_messaging_health_signal


def _provider(*, live_probe_supported: bool):
    return ProviderDefinition(
        provider_key="x",
        title="X",
        connector_id="c",
        adapter_key="a",
        channel_kind=ChannelKind.CHATBOT,
        domain="platform_infra",
        description="d",
        secret_fields=(),
        messaging_channel="telegram",
        messaging_capabilities={"plain_text": True},
        messaging_live_probe_supported=live_probe_supported,
    )


class _Probe:
    def __init__(self, status: str, ok: bool):
        self.status = status
        self.ok = ok


def test_bridge_returns_none_when_live_probe_not_supported():
    signal = resolve_provider_messaging_health_signal(
        provider=_provider(live_probe_supported=False),
        probe_result=_Probe(status="probe_live_failed", ok=False),
    )
    assert signal is None


def test_bridge_returns_signal_for_supported_provider():
    signal = resolve_provider_messaging_health_signal(
        provider=_provider(live_probe_supported=True),
        probe_result=_Probe(status="probe_live_ok", ok=True),
    )
    assert signal is not None
    assert signal.channel == "telegram"
    assert signal.measurable is True
