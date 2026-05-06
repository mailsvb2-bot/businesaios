from __future__ import annotations

from dataclasses import dataclass, field

from execution.blast_radius_guard import BlastRadiusGuard


@dataclass(frozen=True)
class _Req:
    tenant_id: str = "t1"
    autonomy_tier: str = "bounded_autonomy"
    constraints: dict = field(default_factory=dict)
    approval_policy: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


def test_blast_radius_blocks_irreversible_window() -> None:
    guard = BlastRadiusGuard()
    req = _Req(
        constraints={"blast_radius_max_outbound_per_window": 1},
        meta={"previous_feedback": {}},
    )
    decision = guard.evaluate(
        request=req,
        action_type="send_message@v1",
        payload={"recipient_count": 1},
        tenant_id="t1",
        autonomy_tier="bounded_autonomy",
        recent_actions=[{"outbound_count": 1}],
    )
    assert decision.allowed is False
    assert decision.reason == "blast_radius_exceeded"
    assert "blast_radius_max_outbound_per_window" in decision.details["violated_limits"]
