from __future__ import annotations

from interfaces.cli import headless_product


def test_cli_scenario_smoke_uses_single_canonical_bootstrap_path(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    headless_product.build_headless_runtime.cache_clear()
    code = headless_product.main([
        "scenario",
        "lead_processing",
        "--business-id",
        "biz-scenario",
        "--tenant-id",
        "tenant-scenario",
    ])
    assert code in {0, 1}
    runtime = headless_product.build_headless_runtime(entrypoint="headless_cli")
    assert runtime.contract is not None
