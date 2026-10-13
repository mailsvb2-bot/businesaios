"""Case-bound, owner-consented diagnostic access using SupportCaseRegistry facts.

Not a separate authorization database or operator identity. A SUPPORT key alone
never grants access: tenant/business, case claim, owner consent and TTL must all
be true on *every* read. Every diagnostic disclosure writes a canonical fact.
Only bounded counts leave the canonical Event Spine, never raw payloads/PII.
"""
from __future__ import annotations

import time
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from application.business_autonomy.support_case_registry import _key, _required, _scoped_key
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE

_GRANTED = "support_case.access_granted"
_REVOKED = "support_case.access_revoked"
_VIEWED = "support_case.diagnostics_viewed"
_ACCESS_FACTS = frozenset({_GRANTED, _REVOKED, _VIEWED})
CANON_SUPPORT_CASE_DELEGATED_ACCESS = True


class SupportCaseDiagnosticAccess:
    """One projection of the existing SupportCaseRegistry and EventFact writer."""

    def __init__(self, *, support_cases: Any) -> None:
        self._cases = support_cases
        self._events = support_cases._events
        self._writer = support_cases._writer

    def _facts(self, *, tenant_id: str, business_id: str, case_id: str) -> list[tuple[str, dict, int]]:
        from application.business_autonomy.support_case_contract import normalize_support_case_id
        case_id = normalize_support_case_id(case_id)
        # Prove case ownership before any audit facts are exposed.
        self._cases.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        result = []
        for event in self._events.iter_events(
            tenant_id=tenant_id, start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE,
            after_append_seq=0,
        ):
            if event.get("source") != "support_case_registry":
                continue
            row = event.get("payload") or {}
            if (row.get("business_id") != business_id or row.get("entity_id") != case_id
                    or row.get("fact_type") not in _ACCESS_FACTS):
                continue
            payload = row.get("payload")
            seq = event.get("append_seq")
            if not isinstance(payload, dict) or type(seq) is not int or seq <= 0:
                raise RuntimeError("support_access_durable_fact_invalid")
            result.append((row["fact_type"], payload, seq))
        if len({x[2] for x in result}) != len(result):
            raise RuntimeError("support_access_durable_append_sequence_invalid")
        return sorted(result, key=lambda x: x[2])

    def state(self, *, tenant_id: str, business_id: str, case_id: str,
              now_ms: int | None = None) -> dict[str, object]:
        case = self._cases.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        latest = None
        revoked = False
        views = 0
        for kind, row, _ in facts:
            if kind == _GRANTED:
                if (not isinstance(row.get("grant_id"), str)
                        or type(row.get("case_revision")) is not int
                        or type(row.get("issued_at_ms")) is not int
                        or type(row.get("expires_at_ms")) is not int
                        or row["expires_at_ms"] <= row["issued_at_ms"]
                        or not row.get("operator_id") or not row.get("owner_id")):
                    raise RuntimeError("support_access_durable_grant_invalid")
                latest, revoked, views = row, False, 0
            elif kind == _REVOKED:
                if latest is None or revoked or row.get("grant_id") != latest["grant_id"]:
                    raise RuntimeError("support_access_durable_revocation_invalid")
                revoked = True
            elif kind == _VIEWED:
                if latest is None or revoked or row.get("grant_id") != latest["grant_id"]:
                    raise RuntimeError("support_access_durable_view_invalid")
                if not isinstance(row.get("counts"), dict) or not row.get("operator_id"):
                    raise RuntimeError("support_access_durable_view_invalid")
                views += 1
        now = int(time.time() * 1000) if now_ms is None else now_ms
        if type(now) is not int or now < 0:
            raise ValueError("support_access_time_invalid")
        if latest is None:
            reason = "not_granted"
        elif revoked:
            reason = "revoked"
        elif (case["status"] != "claimed"
              or case["claimed_by_operator_user_id"] != latest["operator_id"]
              or case["revision"] != latest["case_revision"]):
            reason = "case_changed"
        elif now >= latest["expires_at_ms"]:
            reason = "expired"
        else:
            reason = "active"
        return {
            "case_id": case["id"], "active": reason == "active", "reason": reason,
            "grant_id": latest["grant_id"] if latest else None,
            "expires_at_ms": latest["expires_at_ms"] if latest else None,
            "views": views, "fact_revision": len(facts),
        }

    def grant(self, *, tenant_id: str, business_id: str, case_id: str,
              owner_id: str, expected_case_revision: int, duration_seconds: int,
              idempotency_key: str, now_ms: int | None = None) -> dict[str, object]:
        owner_id, key = _required(owner_id, "support_access_owner"), _key(idempotency_key)
        if type(expected_case_revision) is not int or expected_case_revision < 1:
            raise ValueError("support_access_revision_invalid")
        if type(duration_seconds) is not int or not 60 <= duration_seconds <= 3600:
            raise ValueError("support_access_duration_invalid")
        now = int(time.time() * 1000) if now_ms is None else now_ms
        case = self._cases.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        effective = _scoped_key(tenant_id=tenant_id, business_id=business_id,
                                case_id=case_id, actor_id=owner_id, raw_key=key)
        prior = self._writer.find_existing_for_key(
            tenant_id=tenant_id, business_id=business_id, entity_id=case["id"],
            operation="grant_access", idempotency_key=effective,
            fact_type=_GRANTED, event_metadata={"actor_id": owner_id},
        )
        if prior is not None:
            payload = prior["payload"]["payload"]
            if (payload["case_revision"] != expected_case_revision
                    or payload["expires_at_ms"]-payload["issued_at_ms"] != duration_seconds*1000):
                raise RuntimeError("support_access_idempotency_conflict")
            return self.state(tenant_id=tenant_id, business_id=business_id, case_id=case["id"], now_ms=now)
        if (case["status"] != "claimed"
                or case["revision"] != expected_case_revision
                or not case["claimed_by_operator_user_id"]):
            raise RuntimeError("support_access_case_not_claimed_or_stale")
        state = self.state(tenant_id=tenant_id, business_id=business_id, case_id=case["id"], now_ms=now)
        if state["active"]:
            raise RuntimeError("support_access_existing_grant_active")
        identifier = str(uuid5(NAMESPACE_URL,
            f"businessaios:support-access:{tenant_id}:{business_id}:{case['id']}:{owner_id}:{key}"))
        row = {
            "grant_id": identifier, "case_revision": case["revision"],
            "owner_id": owner_id, "operator_id": case["claimed_by_operator_user_id"],
            "issued_at_ms": now, "expires_at_ms": now + duration_seconds * 1000,
        }
        try:
            self._writer.append_transition_once(
                tenant_id=tenant_id, business_id=business_id, entity_id=case["id"],
                expected_state_token="access:" + str(state["fact_revision"]),
                operation="grant_access", idempotency_key=effective,
                fact_type=_GRANTED, payload=row, occurred_at_ms=now,
                event_metadata={"actor_id": owner_id},
            )
        except RuntimeError as exc:
            if str(exc).startswith("ontology transition rejected:"):
                raise RuntimeError("support_access_revision_conflict") from exc
            raise
        return self.state(tenant_id=tenant_id, business_id=business_id, case_id=case["id"], now_ms=now)

    def revoke(self, *, tenant_id: str, business_id: str, case_id: str,
               owner_id: str, grant_id: str, idempotency_key: str,
               now_ms: int | None = None) -> dict[str, object]:
        owner_id, key = _required(owner_id, "support_access_owner"), _key(idempotency_key)
        now = int(time.time() * 1000) if now_ms is None else now_ms
        case = self._cases.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        effective = _scoped_key(tenant_id=tenant_id, business_id=business_id,
                                case_id=case["id"], actor_id=owner_id, raw_key=key)
        prior = self._writer.find_existing_for_key(
            tenant_id=tenant_id, business_id=business_id, entity_id=case["id"],
            operation="revoke_access", idempotency_key=effective,
            fact_type=_REVOKED, event_metadata={"actor_id": owner_id},
        )
        if prior is not None:
            if prior["payload"]["payload"].get("grant_id") != grant_id:
                raise RuntimeError("support_access_idempotency_conflict")
            return self.state(tenant_id=tenant_id, business_id=business_id, case_id=case["id"], now_ms=now)
        state = self.state(tenant_id=tenant_id, business_id=business_id, case_id=case["id"], now_ms=now)
        if not state["active"] or state["grant_id"] != grant_id:
            raise RuntimeError("support_access_grant_not_active")
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=case["id"],
            expected_state_token="access:" + str(state["fact_revision"]),
            operation="revoke_access", idempotency_key=effective,
            fact_type=_REVOKED, payload={"grant_id": grant_id, "owner_id": owner_id,
                                         "revoked_at_ms": now},
            occurred_at_ms=now, event_metadata={"actor_id": owner_id},
        )
        return self.state(tenant_id=tenant_id, business_id=business_id, case_id=case["id"], now_ms=now)

    def diagnostics(self, *, tenant_id: str, business_id: str, case_id: str,
                    operator_id: str, idempotency_key: str,
                    now_ms: int | None = None) -> dict[str, object]:
        operator_id, key = _required(operator_id, "support_access_operator"), _key(idempotency_key)
        now = int(time.time() * 1000) if now_ms is None else now_ms
        case = self._cases.get(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        state = self.state(tenant_id=tenant_id, business_id=business_id, case_id=case["id"], now_ms=now)
        if not state["active"] or case["claimed_by_operator_user_id"] != operator_id:
            raise RuntimeError("support_access_no_live_consent")
        effective = _scoped_key(tenant_id=tenant_id, business_id=business_id,
                                case_id=case["id"], actor_id=operator_id, raw_key=key)
        prior = self._writer.find_existing_for_key(
            tenant_id=tenant_id, business_id=business_id, entity_id=case["id"],
            operation="view_diagnostics", idempotency_key=effective,
            fact_type=_VIEWED, event_metadata={"actor_id": operator_id},
        )
        if prior is not None:
            row = prior["payload"]["payload"]
            if row.get("grant_id") != state["grant_id"] or row.get("operator_id") != operator_id:
                raise RuntimeError("support_access_idempotency_conflict")
            return self._diagnostic_receipt(case["id"], row)
        # A fixed coarse, PII-free diagnostic projection; not raw log access.
        counts = {"messages": 0, "payments": 0, "programs": 0, "support": 0}
        for event in self._events.iter_events(
            tenant_id=tenant_id, start_ms=max(0, now - 86_400_000),
            event_type=BUSINESS_FACT_EVENT_TYPE,
        ):
            fact = event.get("payload") or {}
            if fact.get("business_id") != business_id:
                continue
            fact_type = str(fact.get("fact_type") or "")
            group = ("messages" if fact_type.startswith("message.")
                     else "payments" if fact_type.startswith("invoice.")
                     else "programs" if fact_type.startswith("program.")
                     else "support" if fact_type.startswith("support_case.")
                     else None)
            if group:
                counts[group] += 1
        row = {
            "grant_id": state["grant_id"], "operator_id": operator_id,
            "observed_at_ms": now, "window_hours": 24, "counts": counts,
        }
        try:
            self._writer.append_transition_once(
                tenant_id=tenant_id, business_id=business_id, entity_id=case["id"],
                expected_state_token="access:" + str(state["fact_revision"]),
                operation="view_diagnostics", idempotency_key=effective,
                fact_type=_VIEWED, payload=row, occurred_at_ms=now,
                event_metadata={"actor_id": operator_id},
            )
        except RuntimeError as exc:
            if str(exc).startswith("ontology transition rejected:"):
                raise RuntimeError("support_access_revision_conflict") from exc
            raise
        if not self.state(tenant_id=tenant_id, business_id=business_id, case_id=case["id"])["active"]:
            raise RuntimeError("support_access_no_live_consent")
        return self._diagnostic_receipt(case["id"], row)

    @staticmethod
    def _diagnostic_receipt(case_id: str, row: dict) -> dict[str, object]:
        return {"case_id": case_id, "grant_id": row["grant_id"],
                "observed_at_ms": row["observed_at_ms"],
                "window_hours": 24, "counts": dict(row["counts"])}

    def audit(self, *, tenant_id: str, business_id: str, case_id: str) -> dict[str, object]:
        state = self.state(tenant_id=tenant_id, business_id=business_id, case_id=case_id)
        entries = []
        for kind, row, _ in self._facts(tenant_id=tenant_id, business_id=business_id, case_id=case_id):
            if kind == _GRANTED:
                entries.append({"action": "granted", "at_ms": row["issued_at_ms"],
                                "expires_at_ms": row["expires_at_ms"]})
            elif kind == _REVOKED:
                entries.append({"action": "revoked", "at_ms": row["revoked_at_ms"]})
            else:
                entries.append({"action": "diagnostics_viewed", "at_ms": row["observed_at_ms"]})
        return {**state, "entries": entries[-100:], "total": len(entries),
                "truncated": len(entries) > 100}


__all__ = ["CANON_SUPPORT_CASE_DELEGATED_ACCESS", "SupportCaseDiagnosticAccess"]
