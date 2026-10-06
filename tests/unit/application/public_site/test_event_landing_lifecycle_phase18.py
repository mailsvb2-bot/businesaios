from __future__ import annotations

import pytest

from application.public_site.landing_content import EventLandingPublicationStatus, new_event_landing_state
from contracts.landing_page import EventLandingContent, EventLandingFaq

def _content(title: str) -> EventLandingContent:
    return EventLandingContent(eyebrow="Онлайн", hero_title=title, hero_subtitle="Подзаголовок",
        audience_title="Для кого", audience_points=("Для владельцев бизнеса",), outcomes_title="Что получите",
        outcome_points=("Понимание следующего шага",), agenda_title="Программа", agenda_points=("Вводная часть",),
        speaker_title="Организатор", speaker_text="Команда", faq_title="FAQ",
        faq=(EventLandingFaq(question="Когда?", answer="Сегодня."),), cta_title="Регистрация", cta_text="Оставьте данные.")

def test_event_landing_draft_preview_publish_edit_and_unpublish() -> None:
    initial = _content("Первая версия")
    state = new_event_landing_state(event_id="event-1", content=initial)
    assert (state.revision, state.preview(), state.public_content(), state.is_published) == (1, initial, None, False)
    published = state.publish(expected_revision=1)
    assert published.status is EventLandingPublicationStatus.PUBLISHED
    assert (published.public_content(), published.published_revision, published.has_unpublished_changes) == (initial, 1, False)
    edited = published.save_draft(content=_content("Вторая версия"), source="manual", expected_revision=1)
    assert (edited.revision, edited.preview().hero_title, edited.public_content().hero_title, edited.has_unpublished_changes) == (2, "Вторая версия", "Первая версия", True)
    republished = edited.publish(expected_revision=2)
    assert (republished.public_content().hero_title, republished.published_revision, republished.has_unpublished_changes) == ("Вторая версия", 2, False)
    unpublished = republished.unpublish(expected_revision=2)
    assert (unpublished.public_content(), unpublished.is_published, unpublished.preview().hero_title) == (None, False, "Вторая версия")

def test_event_landing_rejects_stale_editor_revision() -> None:
    edited = new_event_landing_state(event_id="event-1", content=_content("A")).save_draft(content=_content("B"), source="manual", expected_revision=1)
    with pytest.raises(RuntimeError, match="event_landing_revision_conflict"):
        edited.save_draft(content=_content("lost update"), source="manual", expected_revision=1)
    with pytest.raises(RuntimeError, match="event_landing_revision_conflict"):
        edited.publish(expected_revision=1)

def test_preview_never_leaks_unpublished_changes_to_public_snapshot() -> None:
    published = new_event_landing_state(event_id="event-1", content=_content("Public")).publish(expected_revision=1)
    draft = published.save_draft(content=_content("Secret draft"), source="ai", expected_revision=1)
    assert (draft.preview().hero_title, draft.public_content().hero_title) == ("Secret draft", "Public")
