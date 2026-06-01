from __future__ import annotations

from application.effects.effect_verification_bridge import (
    extract_router_result_from_feedback,
    normalize_feedback_contract,
)
from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_runtime_router_contract_bridges_into_closed_loop_feedback() -> None:
    router_result = {
        "action_type": "website.publish_page",
        "ok": True,
        "status": "success",
        "verification_status": "verified",
        "verification_confidence": 1.0,
        "external_refs": ["page:verified"],
        "data": {"url": "https://example.test/page"},
        "evidence": {
            "source": "effect_router",
            "action_type": "website.publish_page",
            "status": "verified",
            "summary": "page live",
            "external_refs": ["page:verified"],
            "confidence": 1.0,
            "payload": {"status": "success", "ok": True, "external_id": "pub-1"},
        },
    }
    feedback = normalize_feedback_contract({"evidence": router_result["evidence"]})
    extracted = extract_router_result_from_feedback(feedback)

    assert extracted["verified"] is True
    assert extracted["status"] == "verified"
    assert extracted["external_refs"] == ["page:verified"]


def test_closed_loop_accepts_runtime_router_result_as_source_of_truth() -> None:
    orchestrator = ClosedLoopOrchestrator()
    router_result = {
        "verified": True,
        "status": "verified",
        "confidence": 1.0,
        "external_refs": ["crm:lead:123"],
        "source": "effect_router",
    }
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={"action_type": "crm.write_record", "action_id": "act-bridge"},
            world_state={"meta": {}},
            execution_receipt={"status": "executed", "ok": True},
            feedback={"evidence": {"router_result": dict(router_result)}},
            router_evidence=router_result,
        )
    )
    assert result.verification_result["verified"] is True
    assert result.verification_result["verification"]["source_of_truth"] == "router"
    assert result.verification_result["verification"]["external_refs"] == ["crm:lead:123"]
