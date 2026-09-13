#!/usr/bin/env python3
"""Measured BusinessAIOS gates used by ADOS shadow mode.

The bridge composes already-canonical BusinessAIOS CI gates. It does not
replace repository CI and never converts an unsupported assurance into PASS.
Unsupported strict gates remain unregistered so ADOS reports UNKNOWN honestly.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rust_toolchain_env(cwd: Path) -> dict[str, str]:
    """Expose the repository-pinned installed Rust toolchain via PATH."""
    cargo = shutil.which("cargo")
    rustup = shutil.which("rustup")
    if not cargo or not rustup:
        return {}

    configured_cargo = os.environ.get("CARGO_HOME", "").strip()
    proxy_home = Path(rustup).absolute().parent.parent
    cargo_home = Path(configured_cargo).expanduser() if configured_cargo else proxy_home
    configured_rustup = os.environ.get("RUSTUP_HOME", "").strip()
    rustup_home = Path(configured_rustup).expanduser() if configured_rustup else cargo_home.parent / ".rustup"
    cargo_home = cargo_home.absolute()
    rustup_home = rustup_home.absolute()
    if not (cargo_home / "bin" / "cargo").exists() or not (cargo_home / "bin" / "rustup").exists():
        return {}
    if not rustup_home.is_dir():
        return {}

    toolchain_file = cwd / "rust" / "rust-toolchain.toml"
    if not toolchain_file.is_file():
        return {}
    channel = ""
    for line in toolchain_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("channel") and "=" in stripped:
            channel = stripped.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not channel or any(ch in channel for ch in ("/", "\\")):
        return {}

    candidates = sorted((rustup_home / "toolchains").glob(f"{channel}-*/bin"))
    candidates.extend(
        path for path in [rustup_home / "toolchains" / channel / "bin"] if path.is_dir()
    )
    usable = [path for path in candidates if (path / "cargo").is_file() and (path / "rustc").is_file()]
    if len(usable) != 1:
        return {}
    direct_bin = usable[0].absolute()
    current_path = os.environ.get("PATH", "")
    return {
        "CARGO_HOME": str(cargo_home),
        "RUSTUP_HOME": str(rustup_home),
        "PATH": str(direct_bin) + (os.pathsep + current_path if current_path else ""),
    }


@contextmanager
def isolated_runtime_data_dir() -> Iterator[Path]:
    """Give each measured gate private runtime, temp, and bootstrap roots."""
    names = (
        "BUSINESAIOS_DATA_DIR",
        "DATA_DIR",
        "BAIOS_BOOT_SMOKE_ROOT",
        "RUNNER_TEMP",
        "TMPDIR",
        "TEMP",
        "TMP",
    )
    previous = {name: os.environ.get(name) for name in names}
    with tempfile.TemporaryDirectory(prefix="businesaios-ados-gate-runtime-") as temp_dir:
        runtime_root = Path(temp_dir).resolve()
        try:
            runtime_root.relative_to(ROOT.resolve())
        except ValueError:
            pass
        else:
            raise RuntimeError("ADOS gate runtime directory must be outside the repository")
        data_root = runtime_root / "data"
        temp_root = runtime_root / "tmp"
        runner_temp = runtime_root / "runner-temp"
        boot_root = runtime_root / "boot-smoke"
        for path in (data_root, temp_root, runner_temp, boot_root):
            path.mkdir(parents=True, exist_ok=True)
        os.environ.update(
            {
                "BUSINESAIOS_DATA_DIR": str(data_root),
                "DATA_DIR": str(data_root),
                "BAIOS_BOOT_SMOKE_ROOT": str(boot_root),
                "RUNNER_TEMP": str(runner_temp),
                "TMPDIR": str(temp_root),
                "TEMP": str(temp_root),
                "TMP": str(temp_root),
            }
        )
        try:
            yield runtime_root
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


@contextmanager
def isolated_candidate_worktree() -> Iterator[Path]:
    """Run one gate against an exact disposable detached checkout of HEAD."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="businesaios-ados-worktree-") as parent:
        worktree = Path(parent).resolve() / "candidate"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), head],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            observed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=worktree,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if observed != head:
                raise RuntimeError(
                    f"ADOS gate worktree head mismatch: expected={head} observed={observed}"
                )
            yield worktree
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=ROOT,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=ROOT,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def run(
    command: list[str],
    *,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> None:
    env = os.environ.copy()
    env.update(rust_toolchain_env(cwd))
    if extra_env:
        env.update(extra_env)
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def canonical_gate(
    cwd: Path,
    name: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> None:
    run(
        [sys.executable, "-m", "scripts.ci.cli", "--gate", name],
        cwd=cwd,
        extra_env=extra_env,
    )


def pytest(cwd: Path, *targets: str) -> None:
    run([sys.executable, "-m", "pytest", "-q", *targets], cwd=cwd)


def architecture(cwd: Path) -> None:
    canonical_gate(cwd, "fast")


def tests(cwd: Path) -> None:
    canonical_gate(cwd, "business-critical")


def security(cwd: Path) -> None:
    pytest(cwd, "tests/security")
    canonical_gate(cwd, "rust-safety")


def contracts(cwd: Path) -> None:
    pytest(cwd, "tests/contracts")


def integration(cwd: Path) -> None:
    canonical_gate(cwd, "full")


def user_journey(cwd: Path) -> None:
    canonical_gate(cwd, "acceptance")


def data_migration(cwd: Path) -> None:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:55432/businesaios",
    )
    env = {
        "DATABASE_URL": database_url,
        "POSTGRES_DSN": os.environ.get("POSTGRES_DSN", database_url),
        "POSTGRES_RUNTIME_ENABLED": "1",
        "POSTGRES_EVENT_STORE_ENABLED": "1",
        "POSTGRES_APPLY_MIGRATIONS": "1",
        "RUN_MIGRATIONS_BEFORE_START": "1",
    }
    canonical_gate(cwd, "postgres-migrations", extra_env=env)


def full_regression(cwd: Path) -> None:
    canonical_gate(cwd, "full")


def release_disabled(cwd: Path) -> None:
    del cwd
    print(
        "ADOS Phase 1 is shadow-only: BusinessAIOS build/release certification is intentionally disabled. "
        "Deep Release Validation and Trusted Production Certification remain authoritative.",
        file=sys.stderr,
    )
    raise SystemExit(78)


HANDLERS = {
    "architecture": architecture,
    "tests": tests,
    "security": security,
    "contracts": contracts,
    "integration": integration,
    "user_journey": user_journey,
    "data_migration": data_migration,
    "full_regression": full_regression,
    "release-disabled": release_disabled,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", choices=sorted(HANDLERS))
    args = parser.parse_args()
    with isolated_runtime_data_dir(), isolated_candidate_worktree() as worktree:
        HANDLERS[args.gate](worktree)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
