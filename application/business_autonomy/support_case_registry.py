"""Phase-18 support cases on the canonical Business Event Spine.

This is a product read/write projection, not a second support database or a
new decision core. All mutations use the shared ontology/idempotency writer.
The queue is deliberately tenant+business scoped; platform-wide delegation
requires a separately audited access capability before it can be enabled.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from application.business_autonomy.support_case_contract import (
    SupportCase,
    SupportCaseCategory,
    SupportCaseStatus,
    normalize_support_case_id,
    normalize_support_category,
    normalize_support_summary,
)
from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_scope import hash_scope_seed

_CREATED = "support_case.created"
_CLAIMED = "support_case.claimed"
_RELEASED = "support_case.released"
_RESOLVED = "support_case.resolved"
_TYPES = frozenset({_CREATED, _CLAIMED, _RELEASED, _RESOLVED})
_KEY = re.compile(r"^[a-zA-Z0-9:_-]{1,128}$")


def _required(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 256:
        raise ValueError(f"{label}_required")
    return value.strip()


def _key(value: object) -> str:
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise ValueError("support_case_idempotency_key_invalid")
    return value


def _scoped_key(*, tenant_id: str, business_id: str, case_id: str,
                actor_id: str, raw_key: str) -> str:
    """Bind the client operation key to its own case/actor/business.

    The canonical idempotency store indexes a tenant + namespace + operation +
    *key* independently of semantic scope, rejecting accidental key reuse.
    Two distinct businesses must therefore have distinct effective keys even
    when clients both submit "new-case" or "claim-1". The shared canonical
    idempotency owner still performs the actual reservation and validation.
    """
    return hash_scope_seed(
        "support_case", tenant_id, business_id, case_id, actor_id, raw_key,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def support_case_payload(case: SupportCase, *, revision: int) -> dict[str, object]:
    data = asdict(case)
    data["category"] = case.category.value
    data["status"] = case.status.value
    data["revision"] = revision
    return data


class SupportCaseRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: Any) -> None:
        self._events = event_store
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="support_case", source="support_case_registry",
            id_prefix="support-case",
        )

    def _history(self, *, tenant_id: str, business_id: str, case_id: str | None = None):
        tenant_id = _required(tenant_id, "tenant_id")
        business_id = _required(business_id, "business_id")
        rows = []
        for index, raw in enumerate(self._events.iter_events(
            tenant_id=tenant_id, start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE,
        )):
            if raw.get("source") != "support_case_registry":
                continue
            fact = raw.get("payload") or {}
            if not isinstance(fact, dict) or fact.get("business_id") != business_id or fact.get("fact_type") not in _TYPES:
                continue
            if case_id is not None and fact.get("entity_id") != case_id:
                continue
            payload = fact.get("payload")
            if not isinstance(payload, dict):
                raise RuntimeError("support_case_durable_payload_invalid")
            rows.append((str(fact.get("entity_id") or ""), str(fact["fact_type"]), payload, int(fact.get("event_time_ms") or 0), index))
        rows.sort(key=lambda row: (row[3], row[4]))
        return rows

    @staticmethod
    def _replay(case_id: str, rows):
        if not rows or rows[0][1] != _CREATED:
            raise KeyError("support_case_not_found")
        first = rows[0][2]
        case = SupportCase(
            id=case_id, tenant_id=_required(first["tenant_id"], "tenant_id"),
            business_id=_required(first["business_id"], "business_id"),
            category=SupportCaseCategory(first["category"]),
            summary=normalize_support_summary(first["summary"]),
            status=SupportCaseStatus.OPEN,
            created_by_member_id=_required(first["created_by_member_id"], "created_by_member_id"),
            claimed_by_operator_user_id=None,
            created_at=str(first["created_at"]), updated_at=str(first["created_at"]),
            claimed_at=None, resolved_at=None,
        )
        for _, kind, data, _, _ in rows[1:]:
            from dataclasses import replace
            if kind == _CLAIMED and case.status is SupportCaseStatus.OPEN:
                case = replace(case, status=SupportCaseStatus.CLAIMED,
                    claimed_by_operator_user_id=str(data["operator_id"]),
                    claimed_at=str(data["occurred_at"]), updated_at=str(data["occurred_at"]))
            elif kind == _RELEASED and case.status is SupportCaseStatus.CLAIMED and case.claimed_by_operator_user_id == data.get("operator_id"):
                case = replace(case, status=SupportCaseStatus.OPEN,
                    claimed_by_operator_user_id=None, claimed_at=None, updated_at=str(data["occurred_at"]))
            elif kind == _RESOLVED and case.status is SupportCaseStatus.CLAIMED and case.claimed_by_operator_user_id == data.get("operator_id"):
                case = replace(case, status=SupportCaseStatus.RESOLVED,
                    resolved_at=str(data["occurred_at"]), updated_at=str(data["occurred_at"]))
            else:
                raise RuntimeError("support_case_durable_transition_invalid")
        return case, len(rows)

    def get(self, *, tenant_id: str, business_id: str, case_id: str):
        case_id = normalize_support_case_id(case_id)
        rows = self._history(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        case, revision = self._replay(case_id, rows)
        if case.tenant_id != tenant_id or case.business_id != business_id:
            raise KeyError("support_case_not_found")
        return support_case_payload(case, revision=revision)

    def list(self, *, tenant_id: str, business_id: str, limit: int = 50) -> list[dict[str, object]]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("support_case_limit_invalid")
        grouped: dict[str, list] = {}
        for row in self._history(tenant_id=tenant_id, business_id=business_id):
            grouped.setdefault(row[0], []).append(row)
        cases = []
        for case_id, rows in grouped.items():
            case, revision = self._replay(case_id, rows)
            if case.tenant_id != tenant_id or case.business_id != business_id:
                raise RuntimeError("support_case_durable_scope_invalid")
            cases.append(support_case_payload(case, revision=revision))
        cases.sort(key=lambda case: (str(case["created_at"]), str(case["id"])), reverse=True)
        return cases[:limit]

    def history(self, *, tenant_id: str, business_id: str, case_id: str,
                limit: int = 50) -> dict[str, object]:
        """Owner-visible, immutable case journey from the canonical Event Spine.

        Do not project idempotency keys, raw event envelopes, operator identity,
        or future privileged support-access evidence into the owner interface.
        Read the case first to fail closed if scope or replay is invalid.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("support_case_limit_invalid")
        case_id = normalize_support_case_id(case_id)
        current = self.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        rows = self._history(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        actions = {
            _CREATED: ("created", "open"),
            _CLAIMED: ("claimed", "claimed"),
            _RELEASED: ("released", "open"),
            _RESOLVED: ("resolved", "resolved"),
        }
        entries = []
        for revision, (_, kind, data, _, _) in enumerate(rows, start=1):
            action, status = actions[kind]
            when = data.get("created_at") if kind == _CREATED else data.get("occurred_at")
            if not isinstance(when, str) or not when:
                raise RuntimeError("support_case_durable_timestamp_invalid")
            entries.append({
                "revision": revision,
                "action": action,
                "status": status,
                "occurred_at": when,
            })
        if len(entries) != current["revision"]:
            raise RuntimeError("support_case_durable_revision_invalid")
        return {
            "case_id": case_id,
            "revision": current["revision"],
            "total": len(entries),
            "truncated": len(entries) > limit,
            "entries": entries[-limit:],
        }

    def create(self, *, tenant_id: str, business_id: str, actor_id: str,
               category: SupportCaseCategory | str, summary: str, idempotency_key: str):
        tenant_id, business_id, actor_id = (
            _required(tenant_id, "tenant_id"),
            _required(business_id, "business_id"),
            _required(actor_id, "actor_id"),
        )
        key = _key(idempotency_key)
        category = normalize_support_category(category)
        summary = normalize_support_summary(summary)
        case_id = str(uuid5(NAMESPACE_URL, f"businessaios:support-case:{tenant_id}:{business_id}:{actor_id}:{key}"))
        scoped_key = _scoped_key(
            tenant_id=tenant_id, business_id=business_id, case_id=case_id,
            actor_id=actor_id, raw_key=key,
        )
        try:
            existing = self.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        except KeyError:
            existing = None
        if existing is not None:
            if (existing["category"], existing["summary"], existing["created_by_member_id"]) != (
                category.value, summary, actor_id,
            ):
                raise RuntimeError("support_case_idempotency_conflict")
            durable = self._writer.find_existing_for_key(
                tenant_id=tenant_id, business_id=business_id, entity_id=case_id,
                operation="create", idempotency_key=scoped_key, fact_type=_CREATED,
                event_metadata={"actor_id": actor_id},
            )
            if durable is None:
                raise RuntimeError("support_case_idempotency_conflict")
            return existing
        timestamp = _now()
        payload = {
            "tenant_id": tenant_id, "business_id": business_id,
            "category": category.value, "summary": summary,
            "created_by_member_id": actor_id, "created_at": timestamp,
        }
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=case_id,
            operation="create", idempotency_key=scoped_key,
            fact_type=_CREATED, payload=payload,
            occurred_at_ms=int(datetime.fromisoformat(timestamp).timestamp() * 1000),
            event_metadata={"actor_id": actor_id},
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)

    def transition(self, *, tenant_id: str, business_id: str, case_id: str,
                   operator_id: str, action: str, expected_revision: int,
                   idempotency_key: str):
        tenant_id, business_id = _required(tenant_id, "tenant_id"), _required(business_id, "business_id")
        operator_id, key = _required(operator_id, "operator_id"), _key(idempotency_key)
        case_id = normalize_support_case_id(case_id)
        if action not in {"claim", "release", "resolve"}:
            raise ValueError("support_case_action_invalid")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("support_case_revision_invalid")
        fact_type = {"claim": _CLAIMED, "release": _RELEASED, "resolve": _RESOLVED}[action]
        scoped_key = _scoped_key(
            tenant_id=tenant_id, business_id=business_id, case_id=case_id,
            actor_id=operator_id, raw_key=key,
        )
        replay = self._writer.find_existing_for_key(
            tenant_id=tenant_id, business_id=business_id, entity_id=case_id,
            operation=action, idempotency_key=scoped_key, fact_type=fact_type,
            event_metadata={"actor_id": operator_id},
        )
        if replay is not None:
            prior = dict((replay.get("payload") or {}).get("payload") or {})
            if prior.get("expected_revision") != expected_revision or prior.get("operator_id") != operator_id:
                raise RuntimeError("support_case_idempotency_conflict")
            # A replay acknowledges precisely the original transition, never
            # a subsequent case state after release, reassignment, or resolution.
            current = self.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
            expected_status = {
                "claim": SupportCaseStatus.CLAIMED.value,
                "release": SupportCaseStatus.OPEN.value,
                "resolve": SupportCaseStatus.RESOLVED.value,
            }[action]
            if (
                current["revision"] != expected_revision + 1
                or current["status"] != expected_status
                or (action == "claim" and current["claimed_by_operator_user_id"] != operator_id)
            ):
                raise RuntimeError("support_case_replay_stale")
            return current
        current = self.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        if current["revision"] != expected_revision:
            raise RuntimeError("support_case_revision_conflict")
        if action == "claim" and current["status"] != SupportCaseStatus.OPEN.value:
            raise RuntimeError("support_case_not_open")
        if action in {"release", "resolve"} and (
            current["status"] != SupportCaseStatus.CLAIMED.value or current["claimed_by_operator_user_id"] != operator_id
        ):
            raise RuntimeError("support_case_not_claimed_by_operator")
        stamp = _now()
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=case_id,
            expected_state_token=f"{current['revision']}:{current['status']}:{current['claimed_by_operator_user_id'] or '-'}",
            operation=action, idempotency_key=scoped_key, fact_type=fact_type,
            payload={"operator_id": operator_id, "expected_revision": expected_revision, "occurred_at": stamp},
            occurred_at_ms=int(datetime.fromisoformat(stamp).timestamp() * 1000),
            event_metadata={"actor_id": operator_id},
        )
        return self.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
