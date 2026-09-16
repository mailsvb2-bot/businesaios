from __future__ import annotations

from pathlib import Path

from scripts.ci.subprocess_io import isolated_cargo_target


def test_isolated_cargo_target_prefers_explicit_scratch_root_and_cleans(monkeypatch, tmp_path) -> None:
    scratch = tmp_path / "ram-scratch"
    monkeypatch.setenv("BAIOS_CI_CARGO_TARGET_ROOT", str(scratch))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner-temp"))

    with isolated_cargo_target("safety/core") as env:
        target = Path(env["CARGO_TARGET_DIR"])
        assert target.parent == scratch
        assert target.name.startswith("businesaios-safety-core-")
        assert target.is_dir()
        (target / "proof.txt").write_text("proof", encoding="utf-8")

    assert not target.exists()


def test_isolated_cargo_target_falls_back_to_runner_temp(monkeypatch, tmp_path) -> None:
    runner_temp = tmp_path / "runner-temp"
    monkeypatch.delenv("BAIOS_CI_CARGO_TARGET_ROOT", raising=False)
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))

    with isolated_cargo_target("safety") as env:
        target = Path(env["CARGO_TARGET_DIR"])
        assert target.parent == runner_temp

    assert not target.exists()
