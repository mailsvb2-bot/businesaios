from __future__ import annotations

import pytest

from application.public_site.event_landing_registry import EventLandingRegistry
from contracts.landing_page import EventLandingContent, EventLandingFaq
from reliability.idempotency_store import InMemoryIdempotencyStore


class _EventStore:
    def __init__(self) -> None: self.events=[]
    def append_event(self,event):
        self.events.append({**dict(event), "append_seq": len(self.events) + 1})
    def iter_events(self,*,tenant_id,start_ms,end_ms=None,user_id=None,event_type=None,after_append_seq=None):
        rows = [
            dict(e) for e in self.events
            if e.get("tenant_id") == tenant_id
            and (event_type is None or e.get("event_type") == event_type)
            and int(e.get("timestamp_ms") or 0) >= start_ms
            and (end_ms is None or int(e.get("timestamp_ms") or 0) < end_ms)
            and (after_append_seq is None or e["append_seq"] > after_append_seq)
        ]
        if after_append_seq is None:
            # PostgreSQL's ordinary reads may reorder tied timestamps by ID.
            rows.sort(key=lambda e: (e["timestamp_ms"], e["event_id"]))
            for row in rows:
                row.pop("append_seq")
        else:
            rows.sort(key=lambda e: e["append_seq"])
        return rows
    def count_events(self,*,tenant_id,start_ms,end_ms,user_id=None,event_type=None):
        return len(tuple(self.iter_events(tenant_id=tenant_id,start_ms,end_ms=end_ms,user_id=user_id,event_type=event_type)))


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


def test_foreign_fact_source_cannot_create_or_mutate_public_event_landing() -> None:
    """The shared Event Spine is not a shared write authority for landing state."""
    from contracts.event_store import BusinessFactV1

    events, idempotency = _EventStore(), InMemoryIdempotencyStore()
    registry = EventLandingRegistry(event_store=events, idempotency_store=idempotency)

    def foreign_fact(kind: str, payload: dict, *, timestamp: int, fact_id: str) -> None:
        events.append_event(BusinessFactV1(
            fact_id=fact_id,
            tenant_id="tenant-a",
            business_id="business-a",
            fact_type=kind,
            entity_id="event-1",
            event_time_ms=timestamp,
            observed_at_ms=timestamp,
            source="other_domain",
            payload=payload,
        ).as_event())

    # Even an otherwise well-formed foreign CREATE is not owned by the
    # event-landing registry. It must not make an unpublished page appear.
    foreign_fact(
        "event_landing.created",
        {"content": _content("Foreign").to_payload(), "source": "manual"},
        timestamp=1, fact_id="foreign-create",
    )
    with pytest.raises(KeyError, match="event_landing_not_found"):
        registry.get(tenant_id="tenant-a", business_id="business-a", event_id="event-1")

    created = registry.create(
        tenant_id="tenant-a", business_id="business-a", event_id="event-1",
        content=_content("Canonical"), source="manual",
        idempotency_key="canonical-create", actor_id="owner",
    )
    assert created.revision == 1 and created.draft.hero_title == "Canonical"
    published = registry.transition(
        tenant_id="tenant-a", business_id="business-a", event_id="event-1",
        action="publish", expected_revision=1,
        idempotency_key="canonical-publish", actor_id="owner",
    )
    assert published.public_content().hero_title == "Canonical"

    # A later, matching foreign UNPUBLISH must not revoke the real public page.
    foreign_fact(
        "event_landing.unpublished", {"expected_revision": 1},
        timestamp=10**15, fact_id="foreign-unpublish",
    )
    recovered = EventLandingRegistry(
        event_store=events, idempotency_store=idempotency,
    ).get(tenant_id="tenant-a", business_id="business-a", event_id="event-1")
    assert recovered == published
    assert recovered.is_published
    assert recovered.public_content().hero_title == "Canonical"
    assert len(events.events) == 4


def test_publish_unpublish_publish_cycles_use_unique_canonical_guards() -> None:
    events, claims = _EventStore(), InMemoryIdempotencyStore()
    owner = EventLandingRegistry(event_store=events, idempotency_store=claims)
    fields = dict(tenant_id="tenant-a", business_id="business-a", event_id="event-cycle")
    owner.create(**fields, content=_content("First"), source="manual", idempotency_key="create", actor_id="owner")
    for cycle in range(3):
        published = owner.transition(
            **fields, action="publish", expected_revision=1,
            idempotency_key=f"publish-{cycle}", actor_id="owner",
        )
        assert published.is_published
        assert published.public_content().hero_title == "First"
        unpub = owner.transition(
            **fields, action="unpublish", expected_revision=1,
            idempotency_key=f"unpublish-{cycle}", actor_id="owner",
        )
        assert not unpub.is_published
        assert unpub.public_content() is None
    # Same business event store + idempotency owner, new application instance.
    restarted = EventLandingRegistry(event_store=events, idempotency_store=claims)
    again = restarted.transition(
        **fields, action="publish", expected_revision=1,
        idempotency_key="publish-after-restart", actor_id="owner",
    )
    assert again.is_published
    assert len(events.events) == 8
    assert restarted.get(**fields) == again


def test_competing_create_requests_cannot_append_two_created_facts() -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock

    events, claims = _EventStore(), InMemoryIdempotencyStore()
    registry = EventLandingRegistry(event_store=events, idempotency_store=claims)
    args = dict(tenant_id="tenant-a", business_id="business-a", event_id="raced")
    original_get = registry.get
    gate, lock, seen = Barrier(2), Lock(), [0]

    def simultaneous_missing_read(**kwargs):
        try:
            return original_get(**kwargs)
        except KeyError:
            with lock:
                seen[0] += 1
                first_pair = seen[0] <= 2
            if first_pair:
                gate.wait(timeout=10)
            raise

    registry.get = simultaneous_missing_read

    def create(key):
        try:
            return registry.create(
                **args, content=_content(key), source="manual",
                idempotency_key=key, actor_id="owner",
            ).draft.hero_title
        except RuntimeError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(create, ("one", "two")))
    assert sorted(result).count("event_landing_already_exists") == 1
    assert sum(value in {"one", "two"} for value in result) == 1
    assert len(events.events) == 1
    recovered = EventLandingRegistry(event_store=events, idempotency_store=claims).get(**args)
    assert recovered.draft.hero_title in {"one", "two"}


def test_equal_millisecond_lifecycle_replays_durable_append_order() -> None:
    events, claims = _EventStore(), InMemoryIdempotencyStore()
    registry = EventLandingRegistry(event_store=events, idempotency_store=claims)
    registry._now = lambda: 1234567890000
    scope = dict(tenant_id="tenant-a", business_id="business-a", event_id="same-ms")
    registry.create(**scope, content=_content("First"), source="manual", idempotency_key="create", actor_id="owner")
    registry.transition(**scope, action="publish", expected_revision=1, idempotency_key="publish", actor_id="owner")
    registry.transition(**scope, action="unpublish", expected_revision=1, idempotency_key="unpublish", actor_id="owner")
    registry.transition(**scope, action="publish", expected_revision=1, idempotency_key="republish", actor_id="owner")
    # Make a mock ordinary-query order actively wrong, just like tied
    # timestamps can become ID-ordered in PostgreSQL.
    read_back = list(events.iter_events(tenant_id="tenant-a", start_ms=0, event_type="business_fact.v1"))
    assert {event["timestamp_ms"] for event in read_back} == {1234567890000}
    restarted = EventLandingRegistry(event_store=events, idempotency_store=claims)
    assert restarted.get(**scope).is_published
    assert [r["sequence"] for r in restarted._history(**scope)] == [1, 2, 3, 4]
