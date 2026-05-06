from __future__ import annotations

from runtime.boot.world_snapshot_service import build_world_snapshot_service


def test_world_snapshot_boot_builder_returns_service() -> None:
    service = build_world_snapshot_service()
    assert service.__class__.__name__ == "WorldModelService"
