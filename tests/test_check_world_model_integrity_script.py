from __future__ import annotations

from pathlib import Path

from bootstrap.world_model_forbidden_paths import scan_repo_for_forbidden_world_model_paths


def test_scan_repo_detects_forbidden_patterns(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from core.economics.ltv_world_model import WorldModel\n"
        "x = WorldModel(LTVModel())\n",
        encoding="utf-8",
    )

    findings = scan_repo_for_forbidden_world_model_paths(repo_root=tmp_path)
    assert len(findings) >= 1
    assert any(item["pattern"] == "WorldModel(LTVModel())" for item in findings)
