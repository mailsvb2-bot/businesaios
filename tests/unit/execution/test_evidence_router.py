from __future__ import annotations

from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from execution.evidence.router import build_evidence_router


class StubRequest:
    meta = {}


def test_evidence_router_requires_independent_verification_signal() -> None:
    router = build_evidence_router()
    action = ExecutableAction(
        action_id="a1",
        action_type="create_listing",
        channel="headless",
        payload={},
        decision_id="d1",
        correlation_id="c1",
        objective_name="profit_adjusted_growth",
    )
    action_result = ActionResult(
        action_id="a1",
        status="accepted",
        payload={
            "effector": {
                "verified": True,
                "status": "executed",
                "code": "verified",
                "message": "listing published",
                "external_ref": "listing-42",
                "evidence": {"external_refs": ["listing-42"], "independently_verified": True},
            }
        },
    )
    result = router.verify(request=StubRequest(), action=action, action_result=action_result, connector_result=action_result.payload["effector"])
    assert result.verified is True
    assert result.status == "platforms"
    assert result.external_refs == ("listing-42",)
