"""ClientPlatform multi-lesson publication on BusinessAIOS' canonical Event Spine.

One whole-program fact is atomic: readers can never observe a half-published
course. This is an owner-managed catalog projection, NOT a parallel scheduler,
payments engine or lesson-delivery system. Delivery remains blocked until its
existing canonical execution pipeline is integrated and proven.
"""
from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from application.ontology import EventFactLifecycleWriter
from contracts.customer import CustomerNotFound, CustomerStatus
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_scope import hash_scope_seed

CANON_PHASE18_PROGRAM_PUBLICATION_OWNER = True
_SOURCE = "phase18_program_publication_registry"
_PUBLISHED = "program.published"
_DRAFT_CREATED = "program.draft_created"
_DRAFT_SAVED = "program.draft_saved"
_DRAFT_PUBLISHED = "program.draft_published"
_DRAFT_ARCHIVED = "program.draft_archived"
_PROGRAM_FACTS = frozenset({_PUBLISHED, _DRAFT_CREATED, _DRAFT_SAVED, _DRAFT_PUBLISHED, _DRAFT_ARCHIVED})
_ENROLL_SOURCE = "phase18_program_enrollment_registry"
_ENROLLED = "program.enrollment_created"
_KEY = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")
_CONTENT_KINDS = frozenset({
    "audio", "video", "text", "document", "image", "link", "task", "mixed",
})


def _required(value: object, field: str, *, maximum: int = 200) -> str:
    if not isinstance(value, str):
        raise ValueError(f"program_{field}_invalid")
    result = " ".join(value.split())
    if not result or len(result) > maximum or any(ord(c) < 32 for c in result):
        raise ValueError(f"program_{field}_invalid")
    return result


def _lessons(value: object, *, allow_empty: bool = False) -> list[dict[str, object]]:
    if not isinstance(value, list) or not (0 if allow_empty else 1) <= len(value) <= 100:
        raise ValueError("program_lessons_count_invalid")
    rows = []
    for index, row in enumerate(value, 1):
        if not isinstance(row, dict) or set(row) not in (
            {"title", "content_kind", "content_ref"},
            {"position", "title", "content_kind", "content_ref"},
        ):
            raise ValueError("program_lesson_fields_invalid")
        if "position" in row and (type(row["position"]) is not int or row["position"] != index):
            raise ValueError("program_lesson_position_invalid")
        title = _required(row["title"], "lesson_title")
        kind = _required(row["content_kind"], "content_kind", maximum=16).lower()
        if kind not in _CONTENT_KINDS:
            raise ValueError("program_content_kind_invalid")
        ref = _required(row["content_ref"], "content_ref", maximum=2048)
        if kind == "link":
            parsed = urlsplit(ref)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("program_link_https_required")
        rows.append({"position": index, "title": title, "content_kind": kind, "content_ref": ref})
    return rows


class ProgramPublicationRegistry:
    """Business-scoped immutable publication using the shared ontology writer."""

    def __init__(self, *, event_store: Any, idempotency_store: Any, customer_registry: Any = None) -> None:
        self._events = event_store
        self._customers = customer_registry
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="phase18_program_publication", source=_SOURCE,
            id_prefix="program-publication",
        )
        self._enrollment_writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="phase18_program_enrollment", source=_ENROLL_SOURCE,
            id_prefix="program-enrollment",
        )

    def _records(self, *, tenant_id: str, business_id: str, program_id: str | None = None) -> list[dict[str, object]]:
        tenant_id = _required(tenant_id, "tenant_id")
        business_id = _required(business_id, "business_id")
        grouped: dict[str, list[tuple[int, int, str, dict[str, object]]]] = {}
        for order, event in enumerate(self._events.iter_events(
            tenant_id=tenant_id, start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE,
        )):
            if event.get("source") != _SOURCE:
                continue
            fact = event.get("payload") or {}
            if not isinstance(fact, dict) or fact.get("business_id") != business_id:
                continue
            kind, entity_id = fact.get("fact_type"), fact.get("entity_id")
            if kind not in _PROGRAM_FACTS or not isinstance(entity_id, str):
                raise RuntimeError("program_unknown_durable_fact")
            if program_id is not None and entity_id != program_id:
                continue
            payload = fact.get("payload")
            if not isinstance(payload, dict):
                raise RuntimeError("program_durable_payload_invalid")
            grouped.setdefault(entity_id, []).append((
                int(fact.get("event_time_ms") or 0), order, kind, dict(payload),
            ))
        result: list[dict[str, object]] = []
        for entity_id, facts in grouped.items():
            facts.sort(key=lambda item: (item[0], item[1]))
            first_kind, first_payload = facts[0][2], facts[0][3]
            if first_kind not in {_PUBLISHED, _DRAFT_CREATED}:
                raise RuntimeError("program_durable_creation_missing")
            row = dict(first_payload)
            if row.get("id") != entity_id or row.get("tenant_id") != tenant_id or row.get("business_id") != business_id:
                raise RuntimeError("program_durable_scope_invalid")
            if _required(row.get("title"), "title") != row["title"] or (
                _lessons(row.get("lessons"), allow_empty=first_kind == _DRAFT_CREATED) != row["lessons"]
            ):
                raise RuntimeError("program_durable_content_invalid")
            if row.get("status") != ("active" if first_kind == _PUBLISHED else "draft"):
                raise RuntimeError("program_durable_status_invalid")
            if first_kind == _PUBLISHED and len(facts) != 1:
                raise RuntimeError("program_duplicate_publication")
            revision = 1
            for when, _, kind, payload in facts[1:]:
                if row["status"] != "draft" or payload.get("expected_revision") != revision:
                    raise RuntimeError("program_durable_transition_invalid")
                if kind == _DRAFT_SAVED:
                    if set(payload) != {"expected_revision", "title", "lessons"}:
                        raise RuntimeError("program_durable_payload_invalid")
                    title = _required(payload["title"], "title")
                    lessons = _lessons(payload["lessons"], allow_empty=True)
                    if title != payload["title"] or lessons != payload["lessons"]:
                        raise RuntimeError("program_durable_content_invalid")
                    row.update(title=title, lessons=lessons)
                elif kind == _DRAFT_PUBLISHED:
                    if set(payload) != {"expected_revision"} or not row["lessons"]:
                        raise RuntimeError("program_durable_transition_invalid")
                    row.update(status="active", published_at_ms=when)
                elif kind == _DRAFT_ARCHIVED:
                    if set(payload) != {"expected_revision"}:
                        raise RuntimeError("program_durable_transition_invalid")
                    row.update(status="archived", archived_at_ms=when)
                else:
                    raise RuntimeError("program_durable_transition_invalid")
                revision += 1
                row["revision"] = revision
                row["updated_at_ms"] = when
            result.append(row)
        return result

    def get(self, *, tenant_id: str, business_id: str, program_id: str) -> dict[str, object]:
        program_id = _required(program_id, "id")
        rows = self._records(tenant_id=tenant_id, business_id=business_id, program_id=program_id)
        if not rows:
            raise KeyError("program_not_found")
        if len(rows) != 1:
            raise RuntimeError("program_duplicate_publication")
        return rows[0]

    def list_for_business(self, *, tenant_id: str, business_id: str, limit: int = 50) -> list[dict[str, object]]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("program_limit_invalid")
        rows = [row for row in self._records(tenant_id=tenant_id, business_id=business_id) if row["status"] == "active"]
        if len({row["id"] for row in rows}) != len(rows):
            raise RuntimeError("program_duplicate_publication")
        rows.sort(key=lambda row: (int(row["published_at_ms"]), str(row["id"])), reverse=True)
        return rows[:limit]

    def list_drafts(self, *, tenant_id: str, business_id: str) -> list[dict[str, object]]:
        rows = [row for row in self._records(tenant_id=tenant_id, business_id=business_id) if row["status"] == "draft"]
        rows.sort(key=lambda row: (int(row["created_at_ms"]), str(row["id"])), reverse=True)
        return rows

    def create_draft(self, *, tenant_id: str, business_id: str, actor_id: str,
                     title: str, lessons: object, idempotency_key: str) -> dict[str, object]:
        tenant_id, business_id, actor_id = (_required(tenant_id, "tenant_id"),
                                             _required(business_id, "business_id"),
                                             _required(actor_id, "actor_id"))
        title = _required(title, "title")
        lessons = _lessons(lessons, allow_empty=True)
        if not isinstance(idempotency_key, str) or not _KEY.fullmatch(idempotency_key):
            raise ValueError("program_idempotency_key_invalid")
        draft_id = str(uuid5(NAMESPACE_URL,
            f"businessaios:phase18:program-draft:{tenant_id}:{business_id}:{actor_id}:{idempotency_key}"))
        key = hash_scope_seed("phase18_program_draft", tenant_id, business_id, actor_id, idempotency_key)
        try:
            old = self.get(tenant_id=tenant_id, business_id=business_id, program_id=draft_id)
        except KeyError:
            old = None
        if old is not None:
            initial_facts = [
                dict((event.get("payload") or {}).get("payload") or {})
                for event in self._events.iter_events(
                    tenant_id=tenant_id, start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE,
                )
                if event.get("source") == _SOURCE
                and (event.get("payload") or {}).get("business_id") == business_id
                and (event.get("payload") or {}).get("entity_id") == draft_id
                and (event.get("payload") or {}).get("fact_type") == _DRAFT_CREATED
            ]
            if len(initial_facts) != 1:
                raise RuntimeError("program_durable_creation_invalid")
            initial = initial_facts[0]
            if (initial.get("title") != title or initial.get("lessons") != lessons
                    or initial.get("created_by_actor_id") != actor_id):
                raise RuntimeError("program_idempotency_conflict")
            if not self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=draft_id,
                operation="draft_create", idempotency_key=key,
                fact_type=_DRAFT_CREATED, payload=initial,
                event_metadata={"actor_id": actor_id},
            ):
                raise RuntimeError("program_idempotency_conflict")
            return old
        when = int(time.time() * 1000)
        row = {
            "id": draft_id, "tenant_id": tenant_id, "business_id": business_id,
            "title": title, "status": "draft", "lessons": lessons,
            "created_by_actor_id": actor_id, "created_at_ms": when,
            "updated_at_ms": when, "revision": 1, "published_at_ms": None,
        }
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=draft_id,
            operation="draft_create", idempotency_key=key,
            fact_type=_DRAFT_CREATED, payload=row,
            occurred_at_ms=when, event_metadata={"actor_id": actor_id},
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, program_id=draft_id)

    def change_draft(self, *, tenant_id: str, business_id: str, actor_id: str,
                     program_id: str, action: str, expected_revision: int,
                     idempotency_key: str, title: str | None = None,
                     lessons: object = None) -> dict[str, object]:
        tenant_id, business_id, actor_id = (_required(tenant_id, "tenant_id"),
                                             _required(business_id, "business_id"),
                                             _required(actor_id, "actor_id"))
        if action not in {"save", "publish", "archive"}:
            raise ValueError("program_draft_action_invalid")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("program_expected_revision_invalid")
        if not isinstance(idempotency_key, str) or not _KEY.fullmatch(idempotency_key):
            raise ValueError("program_idempotency_key_invalid")
        program_id = _required(program_id, "id")
        if action == "save":
            payload = {"expected_revision": expected_revision,
                       "title": _required(title, "title"),
                       "lessons": _lessons(lessons, allow_empty=True)}
        else:
            if title is not None or lessons is not None:
                raise ValueError("program_draft_action_fields_invalid")
            payload = {"expected_revision": expected_revision}
        key = hash_scope_seed("phase18_program_draft_change", tenant_id, business_id, actor_id,
                              program_id, idempotency_key)
        kinds = {"save": _DRAFT_SAVED, "publish": _DRAFT_PUBLISHED, "archive": _DRAFT_ARCHIVED}
        metadata = {"actor_id": actor_id}
        existing = self._writer.find_existing_for_key(
            tenant_id=tenant_id, business_id=business_id, entity_id=program_id,
            operation="draft_" + action, idempotency_key=key,
            fact_type=kinds[action], event_metadata=metadata,
        )
        if existing is not None:
            historical_payload = dict((existing.get("payload") or {}).get("payload") or {})
            if historical_payload != payload:
                raise RuntimeError("program_idempotency_conflict")
            return self.get(tenant_id=tenant_id, business_id=business_id, program_id=program_id)
        row = self.get(tenant_id=tenant_id, business_id=business_id, program_id=program_id)
        if row["status"] != "draft":
            raise RuntimeError("program_draft_not_editable")
        if row["revision"] != expected_revision:
            raise RuntimeError("program_revision_conflict")
        if action == "publish" and not row["lessons"]:
            raise ValueError("program_lessons_count_invalid")
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=program_id,
            expected_state_token=f"{expected_revision}:draft",
            operation="draft_" + action, idempotency_key=key,
            fact_type=kinds[action], payload=payload, occurred_at_ms=int(time.time() * 1000),
            event_metadata=metadata,
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, program_id=program_id)

    def publish(
        self, *, tenant_id: str, business_id: str, actor_id: str,
        title: str, lessons: object, idempotency_key: str,
    ) -> dict[str, object]:
        tenant_id = _required(tenant_id, "tenant_id")
        business_id = _required(business_id, "business_id")
        actor_id = _required(actor_id, "actor_id")
        title = _required(title, "title")
        if not isinstance(idempotency_key, str) or not _KEY.fullmatch(idempotency_key):
            raise ValueError("program_idempotency_key_invalid")
        items = _lessons(lessons)
        program_id = str(uuid5(
            NAMESPACE_URL,
            f"businessaios:phase18:program:{tenant_id}:{business_id}:{actor_id}:{idempotency_key}",
        ))
        key = hash_scope_seed(
            "phase18_program_publication", tenant_id, business_id,
            actor_id, idempotency_key,
        )
        try:
            old = self.get(tenant_id=tenant_id, business_id=business_id, program_id=program_id)
        except KeyError:
            old = None
        if old is not None:
            if old["title"] != title or old["lessons"] != items or old["created_by_actor_id"] != actor_id:
                raise RuntimeError("program_idempotency_conflict")
            if not self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=program_id,
                operation="publish", idempotency_key=key, fact_type=_PUBLISHED,
                payload=old, event_metadata={"actor_id": actor_id},
            ):
                raise RuntimeError("program_idempotency_conflict")
            return old
        when = int(time.time() * 1000)
        row: dict[str, object] = {
            "id": program_id, "tenant_id": tenant_id, "business_id": business_id,
            "title": title, "status": "active", "lessons": items,
            "created_by_actor_id": actor_id, "published_at_ms": when,
        }
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=program_id,
            operation="publish", idempotency_key=key, fact_type=_PUBLISHED,
            payload=row, occurred_at_ms=when, event_metadata={"actor_id": actor_id},
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, program_id=program_id)


    def _enrollments(self, *, tenant_id: str, business_id: str,
                     program_id: str | None = None) -> list[dict[str, object]]:
        tenant_id = _required(tenant_id, "tenant_id")
        business_id = _required(business_id, "business_id")
        rows = []
        ids = set()
        for event in self._events.iter_events(
            tenant_id=tenant_id, start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE,
        ):
            if event.get("source") != _ENROLL_SOURCE:
                continue
            fact = event.get("payload") or {}
            if not isinstance(fact, dict) or fact.get("business_id") != business_id:
                continue
            if fact.get("fact_type") != _ENROLLED:
                raise RuntimeError("enrollment_unknown_durable_fact")
            data = fact.get("payload")
            if not isinstance(data, dict):
                raise RuntimeError("enrollment_durable_payload_invalid")
            if data.get("tenant_id") != tenant_id or data.get("business_id") != business_id or (
                data.get("id") != fact.get("entity_id")
            ):
                raise RuntimeError("enrollment_durable_scope_invalid")
            if program_id is not None and data.get("program_id") != program_id:
                continue
            if data["id"] in ids:
                raise RuntimeError("enrollment_duplicate_durable_fact")
            ids.add(data["id"])
            if data.get("status") != "awaiting_delivery" or not isinstance(data.get("progress"), list):
                raise RuntimeError("enrollment_durable_status_invalid")
            program = self.get(
                tenant_id=tenant_id, business_id=business_id,
                program_id=_required(data.get("program_id"), "program_id"),
            )
            expected = [{"position": lesson["position"], "status": "pending"}
                        for lesson in program["lessons"]]
            if data["progress"] != expected or program["status"] != "active":
                raise RuntimeError("enrollment_durable_progress_invalid")
            rows.append(dict(data))
        rows.sort(key=lambda item: (int(item["enrolled_at_ms"]), str(item["id"])), reverse=True)
        return rows

    def enroll_customer(
        self, *, tenant_id: str, business_id: str, actor_id: str,
        program_id: str, customer_id: str,
    ) -> dict[str, object]:
        # No phantom customers or fabricated message delivery. Resolve the
        # customer through the existing canonical customer lifecycle owner.
        tenant_id = _required(tenant_id, "tenant_id")
        business_id = _required(business_id, "business_id")
        actor_id = _required(actor_id, "actor_id")
        try:
            program_id = str(UUID(_required(program_id, "program_id")))
            customer_id = str(UUID(_required(customer_id, "customer_id")))
        except ValueError as exc:
            raise ValueError("enrollment_identifier_invalid") from exc
        program = self.get(tenant_id=tenant_id, business_id=business_id, program_id=program_id)
        if program["status"] != "active":
            raise RuntimeError("enrollment_program_not_active")
        if self._customers is None:
            raise RuntimeError("enrollment_canonical_customer_owner_unavailable")
        try:
            customer = self._customers.get_customer(
                tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
            )
        except CustomerNotFound as exc:
            raise KeyError("enrollment_customer_not_found") from exc
        if customer.customer.status is not CustomerStatus.ACTIVE:
            raise RuntimeError("enrollment_customer_not_active")
        identity = str(uuid5(NAMESPACE_URL,
            f"businessaios:phase18:enrollment:{tenant_id}:{business_id}:{program_id}:{customer_id}",
        ))
        for row in self._enrollments(
            tenant_id=tenant_id, business_id=business_id, program_id=program_id,
        ):
            if row["id"] == identity:
                return row
        now = int(time.time() * 1000)
        row = {
            "id": identity, "tenant_id": tenant_id, "business_id": business_id,
            "program_id": program_id, "customer_id": customer_id,
            "status": "awaiting_delivery",
            "progress": [{"position": lesson["position"], "status": "pending"}
                         for lesson in program["lessons"]],
            "enrolled_at_ms": now,
        }
        key = hash_scope_seed(
            "phase18_program_enrollment", tenant_id, business_id, program_id, customer_id,
        )
        self._enrollment_writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=identity,
            operation="enroll", idempotency_key=key, fact_type=_ENROLLED,
            payload=row, occurred_at_ms=now, event_metadata={"actor_id": actor_id},
        )
        return self.get_enrollment(
            tenant_id=tenant_id, business_id=business_id,
            program_id=program_id, enrollment_id=identity,
        )

    def get_enrollment(
        self, *, tenant_id: str, business_id: str, program_id: str,
        enrollment_id: str,
    ) -> dict[str, object]:
        rows = [row for row in self._enrollments(
            tenant_id=tenant_id, business_id=business_id, program_id=program_id,
        ) if row["id"] == enrollment_id]
        if not rows:
            raise KeyError("program_enrollment_not_found")
        if len(rows) != 1:
            raise RuntimeError("enrollment_duplicate_durable_fact")
        return rows[0]

    def list_enrollments(
        self, *, tenant_id: str, business_id: str, program_id: str,
    ) -> list[dict[str, object]]:
        # Check the parent first, so no other-business program can be probed.
        self.get(tenant_id=tenant_id, business_id=business_id, program_id=program_id)
        return self._enrollments(
            tenant_id=tenant_id, business_id=business_id, program_id=program_id,
        )


__all__ = ["CANON_PHASE18_PROGRAM_PUBLICATION_OWNER", "ProgramPublicationRegistry"]
