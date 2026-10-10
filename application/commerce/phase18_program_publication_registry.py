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
from uuid import NAMESPACE_URL, uuid5

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_scope import hash_scope_seed

CANON_PHASE18_PROGRAM_PUBLICATION_OWNER = True
_SOURCE = "phase18_program_publication_registry"
_PUBLISHED = "program.published"
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


def _lessons(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 100:
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

    def __init__(self, *, event_store: Any, idempotency_store: Any) -> None:
        self._events = event_store
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="phase18_program_publication", source=_SOURCE,
            id_prefix="program-publication",
        )

    def _records(self, *, tenant_id: str, business_id: str, program_id: str | None = None) -> list[dict[str, object]]:
        tenant_id = _required(tenant_id, "tenant_id")
        business_id = _required(business_id, "business_id")
        result: list[dict[str, object]] = []
        for event in self._events.iter_events(
            tenant_id=tenant_id, start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE,
        ):
            if event.get("source") != _SOURCE:
                continue
            fact = event.get("payload") or {}
            if not isinstance(fact, dict) or fact.get("business_id") != business_id:
                continue
            if fact.get("fact_type") != _PUBLISHED:
                raise RuntimeError("program_unknown_durable_fact")
            if program_id is not None and fact.get("entity_id") != program_id:
                continue
            row = fact.get("payload")
            if not isinstance(row, dict) or row.get("id") != fact.get("entity_id"):
                raise RuntimeError("program_durable_payload_invalid")
            if row.get("tenant_id") != tenant_id or row.get("business_id") != business_id:
                raise RuntimeError("program_durable_scope_invalid")
            validated = _lessons(row.get("lessons"))
            if validated != row["lessons"] or _required(row.get("title"), "title") != row["title"]:
                raise RuntimeError("program_durable_content_invalid")
            result.append(dict(row))
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
        rows = self._records(tenant_id=tenant_id, business_id=business_id)
        if len({row["id"] for row in rows}) != len(rows):
            raise RuntimeError("program_duplicate_publication")
        rows.sort(key=lambda row: (int(row["published_at_ms"]), str(row["id"])), reverse=True)
        return rows[:limit]

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


__all__ = ["CANON_PHASE18_PROGRAM_PUBLICATION_OWNER", "ProgramPublicationRegistry"]
