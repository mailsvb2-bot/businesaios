from __future__ import annotations

from pathlib import Path

from execution.autonomy_kill_switch import FileAutonomyKillSwitchRegistry, KillSwitchRule


def test_kill_switch_blocks_matching_scope(tmp_path: Path) -> None:
    registry = FileAutonomyKillSwitchRegistry(root_dir=tmp_path)
    registry.replace_rules([KillSwitchRule(tenant_id="t1", business_id="biz-1", integration_domain="ads_write", action_type="launch_campaign", reason="stop")])
    decision = registry.evaluate(tenant_id="t1", business_id="biz-1", integration_domain="ads_write", action_type="launch_campaign")
    assert decision.active is True
    assert decision.reason == "stop"
