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

def test_rust_toolchain_env_recovers_repository_pinned_rustup_install(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    (repo / "rust").mkdir(parents=True)
    (repo / "rust" / "rust-toolchain.toml").write_text(
        '[toolchain]\nchannel = "1.75.0"\n', encoding="utf-8"
    )
    home = tmp_path / "runner"
    cargo_home = home / ".cargo"
    rustup_home = home / ".rustup"
    proxy_bin = cargo_home / "bin"
    direct_bin = rustup_home / "toolchains" / "1.75.0-x86_64-unknown-linux-gnu" / "bin"
    proxy_bin.mkdir(parents=True)
    direct_bin.mkdir(parents=True)
    for path in (proxy_bin / "cargo", proxy_bin / "rustup", direct_bin / "cargo", direct_bin / "rustc"):
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    monkeypatch.setenv("PATH", str(proxy_bin))
    monkeypatch.delenv("CARGO_HOME", raising=False)
    monkeypatch.delenv("RUSTUP_HOME", raising=False)

    env = bridge.rust_toolchain_env(repo)
    assert env["CARGO_HOME"] == str(cargo_home.absolute())
    assert env["RUSTUP_HOME"] == str(rustup_home.absolute())
    assert env["PATH"].split(os.pathsep)[0] == str(direct_bin.absolute())


def test_rust_toolchain_env_does_not_invent_missing_rustup_home(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    (repo / "rust").mkdir(parents=True)
    (repo / "rust" / "rust-toolchain.toml").write_text(
        '[toolchain]\nchannel = "1.75.0"\n', encoding="utf-8"
    )
    bin_dir = tmp_path / ".cargo" / "bin"
    bin_dir.mkdir(parents=True)
    for name in ("cargo", "rustup"):
        tool = bin_dir / name
        tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("CARGO_HOME", raising=False)
    monkeypatch.delenv("RUSTUP_HOME", raising=False)

    assert bridge.rust_toolchain_env(repo) == {}
