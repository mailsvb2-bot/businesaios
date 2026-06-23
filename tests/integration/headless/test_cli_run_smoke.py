from __future__ import annotations

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
