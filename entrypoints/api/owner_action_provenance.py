from __future__ import annotations

from collections.abc import Mapping

from contracts.owner_decision_provenance import (
    OWNER_DECISION_DRAFT_SOURCE,
    OWNER_DECISION_DRAFT_VERIFICATION,
)
from entrypoints.api.action_models import ExecuteActionRequest
from entrypoints.api.owner_action_draft import OwnerActionDraftProjector
from entrypoints.api.request_context import RequestContext

CANON_OWNER_ACTION_PROVENANCE_BINDING = True


def _text(value: object) -> str:
    return str(value or "").strip()


def bind_verified_owner_action_provenance(
    *,
    request: ExecuteActionRequest,
    request_context: RequestContext,
    projector: OwnerActionDraftProjector | None,
) -> ExecuteActionRequest:
    payload = dict(request.payload or {})
    raw_track = payload.get("track_payload")
    track = dict(raw_track) if isinstance(raw_track, Mapping) else {}
    marked = (
        _text(payload.get("kind")) == OWNER_DECISION_DRAFT_SOURCE
        or _text(track.get("source")) == OWNER_DECISION_DRAFT_SOURCE
        or any(_text(track.get(key)) for key in ("source_run_id", "source_decision_id", "source_action_id"))
    )
    if not marked:
        return request
    if request.action_type != "send_message@v1":
        raise PermissionError("owner_decision_draft_action_type_mismatch")
    if _text(payload.get("kind")) != OWNER_DECISION_DRAFT_SOURCE or _text(track.get("source")) != OWNER_DECISION_DRAFT_SOURCE:
        raise PermissionError("owner_decision_draft_marker_mismatch")
    if projector is None:
        raise RuntimeError("owner_decision_draft_projector_unavailable")

    tenant_id = request_context.validated_tenant_id(required=True)
    business_id = _text(request_context.metadata.get("authenticated_business_id"))
    if not business_id:
        raise PermissionError("owner_decision_draft_business_scope_required")
    if _text(payload.get("business_id")) != business_id:
        raise PermissionError("owner_decision_draft_business_scope_mismatch")

    draft = projector.project(
        tenant_id=tenant_id,
        business_id=business_id,
        run_id=_text(track.get("source_run_id")),
        decision_id=_text(track.get("source_decision_id")),
        action_id=_text(track.get("source_action_id")),
    )
    payload["track_payload"] = {
        "source": OWNER_DECISION_DRAFT_SOURCE,
        "verification": OWNER_DECISION_DRAFT_VERIFICATION,
        "tenant_id": tenant_id,
        "business_id": business_id,
        "run_id": _text(draft.get("run_id")),
        "decision_id": _text(draft.get("decision_id")),
        "action_id": _text(draft.get("action_id")),
        "action_type": _text(draft.get("action_type")),
    }
    return ExecuteActionRequest(action_type=request.action_type, payload=payload)


__all__ = ["CANON_OWNER_ACTION_PROVENANCE_BINDING", "bind_verified_owner_action_provenance"]
