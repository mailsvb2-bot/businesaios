from __future__ import annotations

from collections.abc import Mapping

from contracts.action_intent import ActionIntentV1, ActionIntentV2
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_ACTION_INTENT_EVIDENCE_PROJECTION = True


class ActionIntentBodyUnavailable(LookupError):
    """Canonical closed-loop evidence exists without the full historical intent body."""


class ActionIntentProjectionConflict(ValueError):
    """Persisted intent body conflicts with canonical evidence identity."""


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _project_body(body: Mapping[str, object]) -> ActionIntentV1 | ActionIntentV2:
    schema_version = int(body.get("schema_version") or 0)
    if schema_version == 1:
        required = (
            "intent_id", "tenant_id", "business_id", "decision_id",
            "correlation_id", "action_type", "channel", "requested_by",
        )
        if any(not str(body.get(name) or "").strip() for name in required):
            raise ActionIntentProjectionConflict("action intent body is incomplete")
        intent: ActionIntentV1 | ActionIntentV2 = ActionIntentV1.from_projection(
            intent_id=str(body["intent_id"]),
            tenant_id=str(body["tenant_id"]),
            business_id=str(body["business_id"]),
            decision_id=str(body["decision_id"]),
            correlation_id=str(body["correlation_id"]),
            action_type=str(body["action_type"]),
            channel=str(body["channel"]),
            payload=_mapping(body.get("payload")),
            payload_hash=str(body.get("payload_hash") or ""),
            requested_by=str(body.get("requested_by") or "sovereign_decision"),
            agent_id=str(body.get("agent_id") or body.get("requested_by") or "sovereign_decision"),
            evidence_refs=tuple(str(item) for item in body.get("evidence_refs") or ()),
            derived_fact_ref=str(body.get("derived_fact_ref") or ""),
        )
    elif schema_version == 2:
        required = (
            "action_id", "intent_id", "tenant_id", "business_id", "decision_id",
            "correlation_id", "goal_id", "agent_id", "capability_target", "channel",
        )
        if any(not str(body.get(name) or "").strip() for name in required):
            raise ActionIntentProjectionConflict("action intent v2 body is incomplete")
        intent = ActionIntentV2.from_projection(
            action_id=str(body["action_id"]),
            intent_id=str(body["intent_id"]),
            tenant_id=str(body["tenant_id"]),
            business_id=str(body["business_id"]),
            decision_id=str(body["decision_id"]),
            correlation_id=str(body["correlation_id"]),
            goal_id=str(body["goal_id"]),
            agent_id=str(body["agent_id"]),
            capability_target=str(body["capability_target"]),
            parameters=_mapping(body.get("parameters")),
            payload_hash=str(body.get("payload_hash") or ""),
            expected_value=body.get("expected_value"),
            estimated_cost=body.get("estimated_cost"),
            confidence=body.get("confidence"),
            risk=body.get("risk"),
            reversibility=body.get("reversibility") if isinstance(body.get("reversibility"), bool) else None,
            requested_autonomy=(
                str(body.get("requested_autonomy"))
                if body.get("requested_autonomy") is not None
                else None
            ),
            deadline=body.get("deadline"),
            channel=str(body.get("channel") or ""),
            evidence_refs=tuple(str(item) for item in body.get("evidence_refs") or ()),
            derived_fact_ref=str(body.get("derived_fact_ref") or ""),
        )
    else:
        raise ActionIntentProjectionConflict("action intent schema version conflicts")
    if intent.as_dict() != dict(body):
        raise ActionIntentProjectionConflict("action intent body conflicts with canonical contract")
    return intent


def _validate_record(record: EvidenceRecord, intent: ActionIntentV1 | ActionIntentV2) -> None:
    lineage = dict(record.lineage)
    checks = (
        (record.tenant_id, intent.tenant_id, "tenant"),
        (record.business_id, intent.business_id, "business"),
        (lineage.get("decision", ""), intent.decision_id, "decision"),
    )
    for actual, expected, label in checks:
        if str(actual or "") != str(expected or ""):
            raise ActionIntentProjectionConflict(
                f"action intent {label} identity conflicts with evidence"
            )
    derived = str(lineage.get("derived_fact") or "")
    if derived and derived != intent.derived_fact_ref:
        raise ActionIntentProjectionConflict(
            "action intent derived fact conflicts with evidence"
        )
    if not set(intent.evidence_refs).issubset(set(record.refs)):
        raise ActionIntentProjectionConflict(
            "action intent evidence refs conflict with evidence"
        )
    outcome = _mapping(record.payload.get("business_outcome"))
    if outcome and str(outcome.get("intent_id") or "") != intent.intent_id:
        raise ActionIntentProjectionConflict(
            "action intent identity conflicts with persisted outcome"
        )


class ActionIntentEvidenceProjector:
    """Read-only ActionIntentV1 projection over the canonical EvidenceStore."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        self._evidence = evidence_store

    @staticmethod
    def _is_closed_loop_record(record: EvidenceRecord, *, business_id: str) -> bool:
        return (
            record.scope == "closed_loop"
            and record.source_type == "closed_loop_verification"
            and record.business_id == str(business_id)
            and bool(str(record.lineage.get("decision") or ""))
        )

    def _project_record(self, record: EvidenceRecord) -> ActionIntentV1 | ActionIntentV2:
        body = _mapping(record.payload.get("action_intent"))
        if not body:
            raise ActionIntentBodyUnavailable(
                "historical action intent body is unavailable"
            )
        intent = _project_body(body)
        _validate_record(record, intent)
        return intent

    def get(
        self, *, tenant_id: str, business_id: str, intent_id: str, limit: int = 1000
    ) -> ActionIntentV1 | ActionIntentV2:
        target = str(intent_id or "").strip()
        if not target:
            raise ValueError("intent_id is required")
        matches: list[ActionIntentV1] = []
        for record in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit):
            if not self._is_closed_loop_record(record, business_id=business_id):
                continue
            body = _mapping(record.payload.get("action_intent"))
            if not body:
                continue
            if str(body.get("intent_id") or "") == target:
                matches.append(self._project_record(record))
        if not matches:
            raise LookupError(f"action intent not found: {target}")
        first = matches[0]
        if any(item != first for item in matches[1:]):
            raise ActionIntentProjectionConflict(
                "multiple canonical evidence rows disagree on action intent body"
            )
        return first

    def list_for_business(
        self, *, tenant_id: str, business_id: str, limit: int = 1000
    ) -> tuple[ActionIntentV1 | ActionIntentV2, ...]:
        projected: dict[str, ActionIntentV1 | ActionIntentV2] = {}
        for record in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit):
            if not self._is_closed_loop_record(record, business_id=business_id):
                continue
            if not _mapping(record.payload.get("action_intent")):
                continue
            intent = self._project_record(record)
            prior = projected.get(intent.intent_id)
            if prior is not None and prior != intent:
                raise ActionIntentProjectionConflict(
                    "multiple canonical evidence rows disagree on action intent body"
                )
            projected[intent.intent_id] = intent
        return tuple(projected[key] for key in sorted(projected))

    def legacy_incomplete_count(
        self, *, tenant_id: str, business_id: str, limit: int = 1000
    ) -> int:
        """Count retained lineage-only rows that predate full ActionIntent bodies."""
        return sum(
            1
            for record in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit)
            if self._is_closed_loop_record(record, business_id=business_id)
            and not _mapping(record.payload.get("action_intent"))
        )


__all__ = [
    "ActionIntentBodyUnavailable",
    "ActionIntentEvidenceProjector",
    "ActionIntentProjectionConflict",
    "CANON_ACTION_INTENT_EVIDENCE_PROJECTION",
]
