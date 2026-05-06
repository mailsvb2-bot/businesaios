from __future__ import annotations

from core.growth.ads.creative.pipeline import generate_candidates
from core.llm.contracts import LLMMessage, LLMRequest, LLMResponse
from core.llm.templated import TemplatedLLM
from runtime.llm_provider_factory import resolve_runtime_llm_settings
from runtime.llm_completion_support import read_provider_and_model


class _CanonicalCreativeLLM:
    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        assert req.metadata == {"surface": "ads_creative_generate"}
        return LLMResponse(
            content=(
                "Headline: Заголовок\n"
                "Primary: Основной текст\n"
                "Description: Описание\n"
                "CTA: Learn More"
            ),
            raw={"mode": "unit_test"},
        )


def test_core_templated_llm_uses_canonical_request_contract() -> None:
    llm = TemplatedLLM(seed=1)
    req = LLMRequest(messages=[LLMMessage(role="user", content="Привет")], model="templated")
    resp = llm.generate_sync(req)
    assert resp.content
    assert resp.text == resp.content
    compat = llm.complete(messages=[LLMMessage(role="user", content="Привет")])
    assert compat.content == resp.content


def test_creative_pipeline_accepts_canonical_llm_without_legacy_complete() -> None:
    out = generate_candidates(
        offer_arm="offer_a",
        business_type="Стоматология",
        offer_title="Осмотр",
        offer_details="Без боли",
        llm=_CanonicalCreativeLLM(),
        n=1,
    )
    assert len(out) == 1
    assert out[0].headline == "Заголовок"
    assert out[0].meta["gen"] == "llm"


def test_resolve_runtime_llm_settings_keeps_boot_and_runtime_on_same_defaults() -> None:
    env = {
        "LLM_BASE_URL": "https://override.example/v1",
        "LLM_API_KEY": "secret",
        "LLM_MODEL": "gpt-test",
    }
    provider, base_url, api_key, model, anthropic_version = resolve_runtime_llm_settings(
        provider="openai",
        read_value=lambda name, default: env.get(name, default),
        openai_legacy_keys=("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"),
    )
    assert provider == "openai_compat"
    assert base_url == "https://override.example/v1"
    assert api_key == "secret"
    assert model == "gpt-test"
    assert anthropic_version == "2023-06-01"


def test_read_provider_and_model_respects_explicit_override() -> None:
    provider, model = read_provider_and_model(provider_override="claude", model_override="m-1")
    assert provider == "anthropic"
    assert model == "m-1"
