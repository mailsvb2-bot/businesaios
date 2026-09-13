from __future__ import annotations

import os

from scripts import ados_businesaios_gate as bridge


def test_ados_gate_runtime_data_is_external_ephemeral_and_restored(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", "before-business-data")
    monkeypatch.setenv("DATA_DIR", "before-data")

    with bridge.isolated_runtime_data_dir() as runtime_root:
        assert runtime_root.exists()
        assert os.environ["BUSINESAIOS_DATA_DIR"] == str(runtime_root)
        assert os.environ["DATA_DIR"] == str(runtime_root)
        assert not runtime_root.is_relative_to(bridge.ROOT.resolve())
        marker = runtime_root / "security" / "marker.txt"
        marker.parent.mkdir(parents=True)
        marker.write_text("runtime-only", encoding="utf-8")
        assert marker.is_file()

    assert not runtime_root.exists()
    assert os.environ["BUSINESAIOS_DATA_DIR"] == "before-business-data"
    assert os.environ["DATA_DIR"] == "before-data"


def test_ados_gate_runtime_does_not_use_repository_data_path() -> None:
    with bridge.isolated_runtime_data_dir() as runtime_root:
        repo_data = (bridge.ROOT / "data").resolve()
        assert runtime_root != repo_data
        assert repo_data not in runtime_root.parents
