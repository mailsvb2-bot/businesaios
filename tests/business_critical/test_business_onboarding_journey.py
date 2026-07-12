from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.handlers.profit_sprint_onboarding import (
    handle_onboarding_lead_source,
    handle_onboarding_start,
    handle_onboarding_text,
)


class FakeEffects:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send_message(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
                "external_refs": ["message-1"],
            },
        }


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="canonical-decision",
            correlation_id="canonical-correlation",
        ),
        tenant_id="business-a",
    )


def test_onboarding_start_uses_canonical_decision_identity_and_tenant_delivery() -> None:
    effects = FakeEffects()

    handle_onboarding_start(
        {
            "decision_id": "forged-decision",
            "correlation_id": "forged-correlation",
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "user_id": "user-1",
        },
        effects,
        _env(),
    )

    call = effects.calls[-1]
    assert call["decision_id"] == "canonical-decision"
    assert call["correlation_id"] == "canonical-correlation"
    assert call["tenant_id"] == "business-a"
    assert call["track_payload"] == {
        "tenant_id": "business-a",
        "product_id": "crm-pro",
        "step": "start",
    }


def test_onboarding_text_persists_the_accepted_business_input() -> None:
    effects = FakeEffects()

    handle_onboarding_text(
        {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "user_id": "user-1",
            "step": "business_goal",
            "text": "Увеличить повторные продажи на 20%",
        },
        effects,
        _env(),
    )

    call = effects.calls[-1]
    assert call["text"] == "✅ Принято."
    assert call["track_payload"]["step"] == "business_goal"
    assert call["track_payload"]["value"] == "Увеличить повторные продажи на 20%"
    assert call["track_payload"]["tenant_id"] == "business-a"


def test_onboarding_text_rejects_empty_input_instead_of_confirming_success() -> None:
    effects = FakeEffects()

    with pytest.raises(RuntimeError, match="ONBOARDING_TEXT_REQUIRED"):
        handle_onboarding_text(
            {
                "tenant_id": "business-a",
                "user_id": "user-1",
                "text": "   ",
            },
            effects,
            _env(),
        )

    assert effects.calls == []


def test_onboarding_lead_source_persists_selected_source() -> None:
    effects = FakeEffects()

    handle_onboarding_lead_source(
        {
            "tenant_id": "business-a",
            "product_id": "crm-pro",
            "user_id": "user-1",
            "lead_source": "website-chat",
        },
        effects,
        _env(),
    )

    call = effects.calls[-1]
    assert call["track_payload"] == {
        "tenant_id": "business-a",
        "product_id": "crm-pro",
        "step": "lead_source",
        "lead_source": "website-chat",
    }
