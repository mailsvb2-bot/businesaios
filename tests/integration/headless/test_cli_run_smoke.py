from __future__ import annotations

from types import SimpleNamespace

from interfaces.cli import headless_product


def test_cli_run_smoke_creates_report_and_runtime_state(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    headless_product.build_headless_runtime.cache_clear()
    code = headless_product.main([
        "run",
        "get 10 clients",
        "--business-id",
        "biz-cli",
        "--tenant-id",
        "tenant-cli",
        "--max-steps",
        "1",
        "--quiet",
    ])
    assert code in {0, 1}
    assert any((tmp_path / ".runtime" / "headless_ledger").rglob("*.json"))
    assert any((tmp_path / ".runtime" / "headless_state").rglob("*.json"))


def test_cli_run_forwards_canonical_goal_id(monkeypatch) -> None:
    captured = {}

    class Contract:
        def execute_autopilot(self, request):
            captured["request"] = request
            return SimpleNamespace(completed=True)

    monkeypatch.setattr(
        headless_product,
        "build_headless_runtime",
        lambda **_: SimpleNamespace(contract=Contract()),
    )

    code = headless_product.main([
        "run",
        "grow profit",
        "--business-id",
        "biz-cli",
        "--tenant-id",
        "tenant-cli",
        "--goal-id",
        "goal-profit",
        "--quiet",
    ])

    assert code == 0
    assert captured["request"].goal_id == "goal-profit"
