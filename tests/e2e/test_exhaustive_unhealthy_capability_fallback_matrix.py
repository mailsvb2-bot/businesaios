from __future__ import annotations

from execution.action_catalog import known_action_types
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request


def test_every_unhealthy_capability_blocks_or_routes_to_an_explicit_fallback(tmp_path) -> None:
    cases = 0
    for index, action_type in enumerate(known_action_types()):
        unhealthy = {
            action_type: {
                "enabled": True,
                "healthy": False,
                "health_score": 0.0,
                "evidence_state": "insufficient",
            }
        }
        harness = build_harness(
            tmp_path / str(index),
            scenario=[
                ScenarioStep(
                    action_type=action_type,
                    output={
                        "verified": True,
                        "goal_reached": True,
                        "terminal": True,
                        "external_refs": [f"{action_type}:proof"],
                    },
                )
            ],
            runtime_capabilities=unhealthy,
        )
        report = harness.run(
            make_request(
                goal=f"Exercise unhealthy {action_type}",
                approval_policy={"allow_action_types": [action_type]},
                meta={"runtime_capabilities": unhealthy},
            )
        )
        assert report.steps
        assert action_type not in harness.executor.seen_actions
        step = report.steps[0]
        planning = dict(step.feedback.get("capability_planning") or {})
        assert planning
        if bool(planning.get("fallback_used")):
            assert str(planning.get("action_type") or "") != action_type
            patch = dict(planning.get("payload_patch") or {})
            assert patch.get("capability_fallback_from") == action_type
            assert patch.get("capability_fallback_reason")
        else:
            assert step.status == "blocked_by_policy"
            assert planning.get("allowed") is False
            assert planning.get("reason")
        cases += 1
    assert cases == 45
