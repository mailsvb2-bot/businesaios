from __future__ import annotations

import os
from pathlib import Path

from scripts import ados_businesaios_gate as bridge


def test_ados_gate_runtime_data_is_external_ephemeral_and_restored(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", "before-business-data")
    monkeypatch.setenv("DATA_DIR", "before-data")
    monkeypatch.setenv("BAIOS_BOOT_SMOKE_ROOT", "before-boot")
    monkeypatch.setenv("RUNNER_TEMP", "before-runner-temp")

    with bridge.isolated_runtime_data_dir() as runtime_root:
        assert runtime_root.exists()
        assert os.environ["BUSINESAIOS_DATA_DIR"] == str(runtime_root / "data")
        assert os.environ["DATA_DIR"] == str(runtime_root / "data")
        assert os.environ["BAIOS_BOOT_SMOKE_ROOT"] == str(runtime_root / "boot-smoke")
        assert os.environ["RUNNER_TEMP"] == str(runtime_root / "runner-temp")
        assert os.environ["TMPDIR"] == str(runtime_root / "tmp")
        assert not runtime_root.is_relative_to(bridge.ROOT.resolve())
        marker = runtime_root / "data" / "security" / "marker.txt"
        marker.parent.mkdir(parents=True)
        marker.write_text("runtime-only", encoding="utf-8")
        assert marker.is_file()

    assert not runtime_root.exists()
    assert os.environ["BUSINESAIOS_DATA_DIR"] == "before-business-data"
    assert os.environ["DATA_DIR"] == "before-data"
    assert os.environ["BAIOS_BOOT_SMOKE_ROOT"] == "before-boot"
    assert os.environ["RUNNER_TEMP"] == "before-runner-temp"


def test_ados_gate_runtime_does_not_use_repository_data_path() -> None:
    with bridge.isolated_runtime_data_dir() as runtime_root:
        repo_data = (bridge.ROOT / "data").resolve()
        assert runtime_root != repo_data
        assert repo_data not in runtime_root.parents


def test_ados_gate_uses_exact_disposable_worktree() -> None:
    with bridge.isolated_candidate_worktree() as worktree:
        assert worktree.exists()
        assert worktree != bridge.ROOT.resolve()
        expected = bridge.subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=bridge.ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        observed = bridge.subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert observed == expected
        generated = worktree / "reports" / "integrity" / "proof.txt"
        generated.parent.mkdir(parents=True)
        generated.write_text("ephemeral", encoding="utf-8")
        assert generated.is_file()
        remembered = Path(worktree)

    assert not remembered.exists()
    assert not (bridge.ROOT / "reports" / "integrity" / "proof.txt").exists()
