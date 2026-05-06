from __future__ import annotations

from interfaces.client.headless_client import BusinesAIOSHeadlessClient
from execution.headless_boot import build_headless_runtime


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
