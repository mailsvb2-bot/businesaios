from __future__ import annotations

from types import SimpleNamespace

from execution.headless_boot import build_headless_runtime
from interfaces.client import headless_client
from interfaces.client.headless_client import BusinesAIOSHeadlessClient


def test_sdk_execute_smoke_builds_runtime_without_bootstrap_error(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    build_headless_runtime.cache_clear()
    client = BusinesAIOSHeadlessClient()
    report = client.execute(
        goal="process inbound leads",
        business_id="biz-sdk",
        tenant_id="tenant-sdk",
        max_steps=1,
    )
    assert report is not None
    assert report.goal == "process inbound leads"
    assert any((tmp_path / ".runtime" / "headless_ledger").rglob("*.json"))
    assert any((tmp_path / ".runtime" / "headless_state").rglob("*.json"))


def test_sdk_execute_forwards_canonical_goal_id(monkeypatch) -> None:
    captured = {}

    class Contract:
        def execute_autopilot(self, request):
            captured["request"] = request
            return SimpleNamespace(goal=request.goal)

    monkeypatch.setattr(
        headless_client,
        "build_headless_runtime",
        lambda **_: SimpleNamespace(contract=Contract()),
    )

    report = BusinesAIOSHeadlessClient().execute(
        goal="grow profit",
        business_id="biz-sdk",
        tenant_id="tenant-sdk",
        goal_id="goal-profit",
    )

    assert report.goal == "grow profit"
    assert captured["request"].goal_id == "goal-profit"
