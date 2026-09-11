from __future__ import annotations

import pytest

from entrypoints.api.action_models import ExecuteActionRequest
from entrypoints.api.owner_action_provenance import bind_verified_owner_action_provenance
from entrypoints.api.request_context import RequestContext


class _Projector:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def project(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "run_id": kwargs["run_id"],
            "decision_id": kwargs["decision_id"],
            "action_id": kwargs["action_id"],
            "action_type": "send_message@v1",
        }


def _context(*, business_id: str = "business-a") -> RequestContext:
    return RequestContext(
        tenant_id="tenant-a",
        actor_id="owner-a",
        metadata={"authenticated_business_id": business_id, "authenticated_principal": True},
    )


def _request(*, business_id: str = "business-a", source: str = "owner_decision_draft") -> ExecuteActionRequest:
    return ExecuteActionRequest(
        action_type="send_message@v1",
        payload={
            "business_id": business_id,
            "kind": "owner_decision_draft",
            "user_id": "42",
            "text": "edited by owner",
            "track_payload": {
                "source": source,
                "source_run_id": "run-1",
                "source_decision_id": "decision-1",
                "source_action_id": "action-1",
                "verification": "browser-forged",
                "extra": "must-not-cross-boundary",
            },
        },
    )


def test_owner_decision_draft_is_revalidated_and_rebound_to_authenticated_scope() -> None:
    projector = _Projector()
    result = bind_verified_owner_action_provenance(
        request=_request(),
        request_context=_context(),
        projector=projector,
    )
    assert projector.calls == [{
        "tenant_id": "tenant-a",
        "business_id": "business-a",
        "run_id": "run-1",
        "decision_id": "decision-1",
        "action_id": "action-1",
    }]
    assert result.payload["text"] == "edited by owner"
    assert result.payload["track_payload"] == {
        "source": "owner_decision_draft",
        "verification": "server_ledger",
        "tenant_id": "tenant-a",
        "business_id": "business-a",
        "run_id": "run-1",
        "decision_id": "decision-1",
        "action_id": "action-1",
        "action_type": "send_message@v1",
    }


@pytest.mark.parametrize(
    "candidate,context,error",
    [
        (_request(business_id="business-b"), _context(), "owner_decision_draft_business_scope_mismatch"),
        (_request(source="manual"), _context(), "owner_decision_draft_marker_mismatch"),
        (_request(), RequestContext(tenant_id="tenant-a", metadata={}), "owner_decision_draft_business_scope_required"),
    ],
)
def test_owner_decision_draft_fails_closed_on_scope_or_marker_tampering(candidate, context, error) -> None:
    with pytest.raises(PermissionError, match=error):
        bind_verified_owner_action_provenance(request=candidate, request_context=context, projector=_Projector())


def test_manual_message_does_not_invoke_decision_projector() -> None:
    projector = _Projector()
    request = ExecuteActionRequest(action_type="send_message@v1", payload={"business_id": "business-a", "kind": "owner_manual", "text": "hello"})
    assert bind_verified_owner_action_provenance(request=request, request_context=_context(), projector=projector) is request
    assert projector.calls == []
