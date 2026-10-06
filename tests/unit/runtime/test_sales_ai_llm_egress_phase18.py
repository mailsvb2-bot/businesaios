from __future__ import annotations

from types import SimpleNamespace

import pytest

from config.llm_provider_policy import InMemorySalesAIConsentStore
from runtime._internal.effects_actions import llm_completion_support as support


class _Client:
    def __init__(self, content: str = "advisory evidence") -> None:
        self.requests = []
        self.content = content

    def generate_sync(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            content=self.content,
            finish_reason="stop",
            usage={"input_tokens": 10, "output_tokens": 5},
        )


def _enabled_store() -> tuple[InMemorySalesAIConsentStore, int]:
    store = InMemorySalesAIConsentStore()
    snapshot = store.configure(
        tenant_id="tenant-a",
        business_id="business-a",
        enabled=True,
        provider="openai_compat",
        base_url="https://api.openai.com/v1",
        data_mode="redacted",
        customer_notice_confirmed=True,
        actor="owner",
        reason="enable sales ai",
    )
    return store, snapshot.consent_epoch


def test_sales_ai_llm_redacts_before_provider_call_and_binds_scope(monkeypatch) -> None:
    store, epoch = _enabled_store()
    client = _Client()
    monkeypatch.setattr(
        support,
        "_configured_client",
        lambda **_: (
            "openai_compat",
            "https://api.openai.com/v1",
            "gpt-test",
            client,
            None,
        ),
    )

    result = support.call_sales_ai_llm(
        tenant_id="tenant-a",
        business_id="business-a",
        provider="openai_compat",
        system="Return observations only.",
        user="Mail me at user@example.com, profile @customer",
        model="gpt-test",
        expected_epoch=epoch,
        consent_store=store,
    )

    assert result["ok"] is True
    assert result["consent_epoch"] == epoch
    assert result["text_was_redacted"] is True
    assert len(client.requests) == 1
    request = client.requests[0]
    assert "user@example.com" not in request.messages[1].content
    assert "@customer" not in request.messages[1].content
    assert request.metadata["tenant_id"] == "tenant-a"
    assert request.metadata["business_id"] == "business-a"
    assert request.metadata["consent_epoch"] == epoch
    assert request.metadata["surface"] == "sales_ai"


def test_sales_ai_llm_rejects_provider_target_change_before_network(monkeypatch) -> None:
    store, epoch = _enabled_store()
    client = _Client()
    monkeypatch.setattr(
        support,
        "_configured_client",
        lambda **_: (
            "yandexgpt",
            "https://llm.api.cloud.yandex.net/foundationModels/v1",
            "yandexgpt",
            client,
            None,
        ),
    )

    with pytest.raises(PermissionError, match="provider_target_changed"):
        support.call_sales_ai_llm(
            tenant_id="tenant-a",
            business_id="business-a",
            provider="yandexgpt",
            system="observations",
            user="hello",
            model=None,
            expected_epoch=epoch,
            consent_store=store,
        )
    assert client.requests == []


def test_sales_ai_llm_rejects_stale_epoch_before_network(monkeypatch) -> None:
    store, epoch = _enabled_store()
    client = _Client()
    monkeypatch.setattr(
        support,
        "_configured_client",
        lambda **_: (
            "openai_compat",
            "https://api.openai.com/v1",
            "gpt-test",
            client,
            None,
        ),
    )
    store.configure(
        tenant_id="tenant-a",
        business_id="business-a",
        enabled=True,
        provider="openai_compat",
        base_url="https://api.openai.com/v1",
        data_mode="redacted",
        customer_notice_confirmed=True,
        actor="owner",
        reason="renew consent",
        expected_revision=1,
    )

    with pytest.raises(PermissionError, match="consent_epoch_changed"):
        support.call_sales_ai_llm(
            tenant_id="tenant-a",
            business_id="business-a",
            provider="openai_compat",
            system="observations",
            user="hello",
            model=None,
            expected_epoch=epoch,
            consent_store=store,
        )
    assert client.requests == []


def test_sales_ai_llm_disabled_consent_never_calls_provider(monkeypatch) -> None:
    store, epoch = _enabled_store()
    revoked = store.configure(
        tenant_id="tenant-a",
        business_id="business-a",
        enabled=False,
        provider="openai_compat",
        base_url="https://api.openai.com/v1",
        data_mode="no_cloud",
        customer_notice_confirmed=False,
        actor="owner",
        reason="revoke",
        expected_revision=1,
    )
    client = _Client()
    monkeypatch.setattr(
        support,
        "_configured_client",
        lambda **_: (
            "openai_compat",
            "https://api.openai.com/v1",
            "gpt-test",
            client,
            None,
        ),
    )

    with pytest.raises(PermissionError, match="consent_disabled"):
        support.call_sales_ai_llm(
            tenant_id="tenant-a",
            business_id="business-a",
            provider="openai_compat",
            system="observations",
            user="hello",
            model=None,
            expected_epoch=revoked.consent_epoch,
            consent_store=store,
        )
    assert revoked.consent_epoch > epoch
    assert client.requests == []


def test_sales_ai_provider_unavailable_is_explicit_not_fake_success(monkeypatch) -> None:
    store, epoch = _enabled_store()
    monkeypatch.setattr(
        support,
        "_configured_client",
        lambda **_: (
            "openai_compat",
            "https://api.openai.com/v1",
            "gpt-test",
            None,
            "missing_api_key",
        ),
    )

    result = support.call_sales_ai_llm(
        tenant_id="tenant-a",
        business_id="business-a",
        provider="openai_compat",
        system="observations",
        user="hello",
        model=None,
        expected_epoch=epoch,
        consent_store=store,
    )
    assert result["ok"] is False
    assert result["error"] == "missing_api_key"
    assert result["consent_epoch"] == epoch


_VALID_ANALYSIS = """{
  "intent": "service_interest",
  "need_summary": "Клиент интересуется услугой",
  "purchase_readiness": 0.8,
  "confidence": 0.9,
  "pricing_question": false,
  "pricing_exception": false,
  "need_is_specific": true,
  "purchase_intent_explicit": true,
  "explicit_human_request": false,
  "sensitive_context": false,
  "negative_sentiment": false,
  "reply_goal": "ask_qualification",
  "reason": "Нужно уточнить задачу"
}"""


def test_sales_ai_analysis_returns_only_validated_evidence_and_decision_inputs(monkeypatch) -> None:
    store, epoch = _enabled_store()
    client = _Client(_VALID_ANALYSIS)
    monkeypatch.setattr(
        support,
        "_configured_client",
        lambda **_: (
            "openai_compat",
            "https://api.openai.com/v1",
            "gpt-test",
            client,
            None,
        ),
    )

    result = support.analyze_sales_ai_message(
        tenant_id="tenant-a",
        business_id="business-a",
        provider="openai_compat",
        customer_text="Хочу узнать подробнее",
        current_stage="engaged",
        source_kind="telegram",
        model="gpt-test",
        expected_epoch=epoch,
        consent_store=store,
    )

    assert result["ok"] is True
    assert result["observation"]["intent"] == "service_interest"
    assert result["decision_inputs"]["evidence_score"] == 0.8
    assert "action_kind" not in result["decision_inputs"]
    assert "event" not in result["decision_inputs"]
    assert "status" not in result["decision_inputs"]
    assert "text" not in result


@pytest.mark.parametrize(
    "content",
    (
        "not-json",
        """{
          "intent": "service_interest",
          "need_summary": "Интерес",
          "purchase_readiness": 0.8,
          "confidence": 0.9,
          "pricing_question": false,
          "pricing_exception": false,
          "need_is_specific": true,
          "purchase_intent_explicit": true,
          "explicit_human_request": false,
          "sensitive_context": false,
          "negative_sentiment": false,
          "reply_goal": "ask_qualification",
          "reason": "Наблюдение",
          "action_kind": "send_message"
        }""",
    ),
)
def test_sales_ai_analysis_rejects_malformed_or_action_bearing_model_output(
    monkeypatch,
    content: str,
) -> None:
    store, epoch = _enabled_store()
    client = _Client(content)
    monkeypatch.setattr(
        support,
        "_configured_client",
        lambda **_: (
            "openai_compat",
            "https://api.openai.com/v1",
            "gpt-test",
            client,
            None,
        ),
    )

    result = support.analyze_sales_ai_message(
        tenant_id="tenant-a",
        business_id="business-a",
        provider="openai_compat",
        customer_text="hello",
        current_stage="new",
        source_kind="telegram",
        model=None,
        expected_epoch=epoch,
        consent_store=store,
    )

    assert result["ok"] is False
    assert result["error"] == "sales_ai_invalid_structured_output"
    assert "text" not in result
    assert len(client.requests) == 1
