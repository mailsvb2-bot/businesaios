from __future__ import annotations

from datetime import timedelta

from governance.kill_switch_registry import KillSwitchEntry, KillSwitchRegistry, _utc_now


def test_kill_switch_registry_blocks_by_tenant() -> None:
    registry = KillSwitchRegistry()
    registry.activate(
        KillSwitchEntry(
            switch_id="sw-1",
            scope="tenant",
            scope_id="tenant-a",
            reason="incident",
            activated_by="security-1",
            activated_at=_utc_now(),
        )
    )

    blocker = registry.find_blocker(
        tenant_id="tenant-a",
        action_name="send_email",
        action_category="outbound",
    )
    assert blocker is not None
    assert blocker.reason == "incident"


def test_kill_switch_registry_auto_expires() -> None:
    registry = KillSwitchRegistry()
    registry.activate(
        KillSwitchEntry(
            switch_id="sw-2",
            scope="action",
            scope_id="send_email",
            reason="temporary_stop",
            activated_by="security-1",
            activated_at=_utc_now() - timedelta(seconds=5),
            expires_at=_utc_now() - timedelta(seconds=1),
        )
    )

    blocker = registry.find_blocker(
        tenant_id="tenant-a",
        action_name="send_email",
        action_category="outbound",
    )
    assert blocker is None
