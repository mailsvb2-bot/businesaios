from __future__ import annotations

from datetime import datetime, timezone

import pytest

from application.public_site.landing_content import (
    BusinessLandingFacts,
    EventLandingFacts,
    build_event_landing_template,
    minimize_event_landing_ai_context,
)
from contracts.landing_page import EventLandingContent


def test_event_landing_template_is_deterministic_and_fact_bounded() -> None:
    event = EventLandingFacts(
        title="Практикум по продажам",
        description="Разберём воронку. Сформируем следующий шаг.",
        timezone_name="UTC",
        starts_at=(datetime(2026, 10, 10, 16, 0, tzinfo=timezone.utc),),
    )
    business = BusinessLandingFacts(
        business_name="Школа",
        activity_description="Обучение",
        confirmed_audiences=("Владельцам малого бизнеса",),
    )
    first = build_event_landing_template(event=event, business=business)
    second = build_event_landing_template(event=event, business=business)
    assert first == second
    assert first.hero_title == "Практикум по продажам"
    assert first.audience_points == ("Владельцам малого бизнеса",)
    assert "10.10.2026" in first.agenda_points[0]


def test_event_landing_contract_rejects_unknown_fields() -> None:
    content = build_event_landing_template(event=EventLandingFacts(title="Событие"))
    payload = content.to_payload()
    payload["customer_email"] = "secret@example.test"
    with pytest.raises(ValueError, match="unsupported fields"):
        EventLandingContent.from_payload(payload)


def test_ai_context_excludes_participant_and_provider_secrets() -> None:
    event = EventLandingFacts(title="Событие", description="Описание")
    business = BusinessLandingFacts(business_name="Компания")
    safe = build_event_landing_template(event=event, business=business)
    payload = minimize_event_landing_ai_context(event=event, business=business, safe_template=safe)
    text = repr(payload).lower()
    for forbidden in ("email", "phone", "token", "credential", "participant", "join_url"):
        assert forbidden not in text
