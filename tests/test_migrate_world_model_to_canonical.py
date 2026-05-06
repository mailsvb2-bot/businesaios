from __future__ import annotations

from pathlib import Path

from scripts.migrate_world_model_to_canonical import migrate_file


def test_migrate_file_rewrites_legacy_world_model(tmp_path: Path):
    file_path = tmp_path / "legacy.py"
    file_path.write_text(
        "from core.economics.ltv_world_model import WorldModel, LTVModel\n"
        "\n"
        "def build():\n"
        "    return WorldModel(LTVModel())\n",
        encoding="utf-8",
    )

    result = migrate_file(file_path)
    rewritten = file_path.read_text(encoding="utf-8")

    assert result.changed is True
    assert "build_default_world_model()" in rewritten
    assert "from bootstrap.world_model_builder import build_default_world_model" in rewritten
    assert "WorldModel(LTVModel())" not in rewritten
