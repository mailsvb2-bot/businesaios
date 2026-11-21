"""Without explicit configuration the marketing LLM must default to a Russian provider."""

from __future__ import annotations

from runtime.boot.builders.marketing_llm import _provider_settings

_KEYS = ("LLM_PROVIDER", "MARKETING_LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL",
         "OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL", "YANDEXGPT_BASE_URL", "YANDEXGPT_API_KEY", "YANDEXGPT_MODEL")


def test_unconfigured_marketing_llm_defaults_to_yandexgpt_not_openai(monkeypatch):
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)
    provider, base_url, _api_key, model, _version = _provider_settings(None)
    assert provider == "yandexgpt"
    assert "openai.com" not in base_url and "anthropic.com" not in base_url
    assert base_url.startswith("https://llm.api.cloud.yandex.net/")
    assert model == "yandexgpt-lite"


def test_explicit_provider_is_still_respected(monkeypatch):
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gigachat")
    assert _provider_settings(None)[0] == "gigachat"
