from core.traffic.creative_generator import CreativeGenerator
from runtime.boot.builders.campaign_builder import build_autopilot_campaign_builder


class RawClient:
    calls = 0
    def generate_sync(self, request):
        RawClient.calls += 1
        raise AssertionError("unaccounted LLM provider call")


def test_raw_llm_cannot_be_used_for_ad_creatives(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "1")
    builder = build_autopilot_campaign_builder(llm_client=RawClient())
    assert builder.traffic.creative_generator.__class__ is CreativeGenerator
    assert RawClient.calls == 0
