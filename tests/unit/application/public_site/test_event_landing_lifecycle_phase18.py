from __future__ import annotations

import pytest

from application.public_site.event_landing_lifecycle import (
    EventLandingPublicationStatus,
    new_event_landing_state,
)
from contracts.landing_page import EventLandingContent, EventLandingFaq


def _content(title: str) -> EventLandingContent:
    return EventLandingContent(
        eyebrow="Онлайн",
        hero_title=title,
        hero_subtitle="Подзаголовок",
        audience_title="Для кого",
        audience_points=("Для владельцев бизнеса",),
        outcomes_title="Что получите",
        outcome_points=("Понимание следующего шага",),
        agenda_title="Программа",
        agenda_points=("Вводная часть",),
        speaker_title="Организатор",
        speaker_text="Команда",
        faq_title="FAQ",
        faq=(EventLandingFaq(question="Когда?", answer="Сегодня."),),
        cta_title="Регистрация",
        cta_text="Оставьте данные.",
    )


def test_event_landing_draft_preview_publish_edit_and_unpublish() -> None:
    initial = _content("Первая версия")
    state = new_event_landing_state(event_id="event-1", content=initial)

    assert state.revision == 1
    assert state.preview() == initial
    assert state.public_content() is None
    assert state.is_published is False

    published = state.publish(expected_revision=1)
    assert published.status is EventLandingPublicationStatus.PUBLISHED
    assert published.public_content() == initial
    assert published.published_revision == 1
    assert published.has_unpublished_changes is False

    edited = published.save_draft(
        content=_content("Вторая версия"),
        source="manual",
        expected_revision=1,
    )
    assert edited.revision == 2
    assert edited.preview().hero_title == "Вторая версия"
    assert edited.public_content().hero_title == "Первая версия"
    assert edited.has_unpublished_changes is True

    republished = edited.publish(expected_revision=2)
    assert republished.public_content().hero_title == "Вторая версия"
    assert republished.published_revision == 2
    assert republished.has_unpublished_changes is False

    unpublished = republished.unpublish(expected_revision=2)
    assert unpublished.public_content() is None
    assert unpublished.is_published is False
    assert unpublished.preview().hero_title == "Вторая версия"


def test_event_landing_rejects_stale_editor_revision() -> None:
    state = new_event_landing_state(event_id="event-1", content=_content("A"))
    edited = state.save_draft(
        content=_content("B"),
        source="manual",
        expected_revision=1,
    )
    with pytest.raises(RuntimeError, match="event_landing_revision_conflict"):
        edited.save_draft(
            content=_content("lost update"),
            source="manual",
            expected_revision=1,
        )
    with pytest.raises(RuntimeError, match="event_landing_revision_conflict"):
        edited.publish(expected_revision=1)


def test_preview_never_leaks_unpublished_changes_to_public_snapshot() -> None:
    original = new_event_landing_state(event_id="event-1", content=_content("Public"))
    published = original.publish(expected_revision=1)
    draft = published.save_draft(
        content=_content("Secret draft"),
        source="ai",
        expected_revision=1,
    )

    assert draft.preview().hero_title == "Secret draft"
    assert draft.public_content().hero_title == "Public"
