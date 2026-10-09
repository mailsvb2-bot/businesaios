from __future__ import annotations

import pytest

from application.public_site.event_landing_registry import EventLandingRegistry
from contracts.landing_page import EventLandingContent, EventLandingFaq
from reliability.idempotency_store import InMemoryIdempotencyStore


class _EventStore:
    def __init__(self) -> None: self.events=[]
    def append_event(self,event): self.events.append(dict(event))
    def iter_events(self,*,tenant_id,start_ms,end_ms=None,user_id=None,event_type=None):
        return [e for e in self.events if e.get("tenant_id")==tenant_id and (event_type is None or e.get("event_type")==event_type)]
    def count_events(self,*,tenant_id,start_ms,end_ms,user_id=None,event_type=None):
        return len(tuple(self.iter_events(tenant_id=tenant_id,start_ms=start_ms,end_ms=end_ms,user_id=user_id,event_type=event_type)))


def _content(title: str) -> EventLandingContent:
    return EventLandingContent(
        eyebrow="Онлайн",hero_title=title,hero_subtitle="Подзаголовок",
        audience_title="Для кого",audience_points=("Владельцы бизнеса",),
        outcomes_title="Результат",outcome_points=("Понимание следующего шага",),
        agenda_title="Программа",agenda_points=("Шаг 1",),speaker_title="Спикер",
        speaker_text="Команда",faq_title="FAQ",faq=(EventLandingFaq(question="Когда?",answer="Сегодня."),),
        cta_title="Регистрация",cta_text="Оставьте данные.",
    )


def test_event_landing_registry_survives_restart_and_replays_same_mutation() -> None:
    events,idempotency=_EventStore(),InMemoryIdempotencyStore()
    registry=EventLandingRegistry(event_store=events,idempotency_store=idempotency)
    created=registry.create(tenant_id="tenant-a",business_id="business-a",event_id="event-1",content=_content("Draft"),source="manual",idempotency_key="create-1",actor_id="owner")
    assert (created.revision,created.is_published)==(1,False)
    published=registry.transition(tenant_id="tenant-a",business_id="business-a",event_id="event-1",action="publish",expected_revision=1,idempotency_key="publish-1",actor_id="owner")
    assert published.public_content().hero_title=="Draft"

    restarted=EventLandingRegistry(event_store=events,idempotency_store=idempotency)
    recovered=restarted.get(tenant_id="tenant-a",business_id="business-a",event_id="event-1")
    assert (recovered.status.value,recovered.published_revision,recovered.public_content().hero_title)==("published",1,"Draft")
    replayed=restarted.transition(tenant_id="tenant-a",business_id="business-a",event_id="event-1",action="publish",expected_revision=1,idempotency_key="publish-1",actor_id="owner")
    assert replayed==recovered
    assert len(events.events)==2


def test_event_landing_registry_fails_closed_on_scope_and_revision_conflicts() -> None:
    events,idempotency=_EventStore(),InMemoryIdempotencyStore()
    registry=EventLandingRegistry(event_store=events,idempotency_store=idempotency)
    registry.create(tenant_id="tenant-a",business_id="business-a",event_id="event-1",content=_content("A"),source="manual",idempotency_key="create-1",actor_id="owner")
    with pytest.raises(KeyError):
        registry.get(tenant_id="tenant-a",business_id="business-b",event_id="event-1")
    with pytest.raises(RuntimeError,match="already_exists"):
        registry.create(tenant_id="tenant-a",business_id="business-a",event_id="event-1",content=_content("A"),source="manual",idempotency_key="create-2",actor_id="owner")
    with pytest.raises(RuntimeError,match="revision_conflict"):
        registry.transition(tenant_id="tenant-a",business_id="business-a",event_id="event-1",action="publish",expected_revision=99,idempotency_key="publish-stale",actor_id="owner")


def test_invalid_event_landing_source_and_identity_never_poison_canonical_history() -> None:
    events, claims = _EventStore(), InMemoryIdempotencyStore()
    registry = EventLandingRegistry(event_store=events, idempotency_store=claims)
    for bad_event_id, bad_source in (
        ("", "manual"), ("e" * 201, "manual"), ("event-1", "untrusted-provider"),
    ):
        with pytest.raises(ValueError):
            registry.create(
                tenant_id="tenant-a", business_id="business-a", event_id=bad_event_id,
                content=_content("Draft"), source=bad_source,
                idempotency_key="bad-" + bad_source + "-" + str(len(bad_event_id)),
                actor_id="owner",
            )
        assert events.events == [], "rejected create must not append a replay-breaking fact"

    created = registry.create(
        tenant_id="tenant-a", business_id="business-a", event_id="event-1",
        content=_content("Draft"), source="manual", idempotency_key="create-good", actor_id="owner",
    )
    assert created.revision == 1
    original = list(events.events)
    with pytest.raises(ValueError):
        registry.transition(
            tenant_id="tenant-a", business_id="business-a", event_id="event-1",
            action="save", expected_revision=1, idempotency_key="bad-save",
            actor_id="owner", content=_content("Updated"), source="untrusted-provider",
        )
    assert events.events == original
    assert registry.get(tenant_id="tenant-a", business_id="business-a", event_id="event-1") == created

    updated = registry.transition(
        tenant_id="tenant-a", business_id="business-a", event_id="event-1",
        action="save", expected_revision=1, idempotency_key="save-good",
        actor_id="owner", content=_content("Updated"), source="manual",
    )
    assert updated.revision == 2



def test_reused_landing_idempotency_key_may_not_mutate_authorized_payload() -> None:
    events, claims = _EventStore(), InMemoryIdempotencyStore()
    registry = EventLandingRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="t", business_id="b", event_id="e", content=_content("A"),
        source="manual", idempotency_key="create", actor_id="owner",
    )
    published = registry.transition(
        tenant_id="t", business_id="b", event_id="e", action="publish",
        expected_revision=1, idempotency_key="publish", actor_id="owner",
    )
    assert published.is_published
    rows = list(events.events)
    assert registry.transition(
        tenant_id="t", business_id="b", event_id="e", action="publish",
        expected_revision=1, idempotency_key="publish", actor_id="owner",
    ) == published
    with pytest.raises(ValueError, match="idempotency_payload_conflict"):
        registry.transition(
            tenant_id="t", business_id="b", event_id="e", action="publish",
            expected_revision=2, idempotency_key="publish", actor_id="owner",
        )
    assert events.events == rows
