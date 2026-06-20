from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.ci.paths import repo_root

DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("CI_STEP_TIMEOUT_SECONDS", "90"))
PYTEST_REQUIRED_PLUGINS = ("pytest_asyncio.plugin",)

PRESERVED_ENV_KEYS = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TZ",
    "TMPDIR",
    "LD_LIBRARY_PATH",
    "GITHUB_ACTIONS",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_JOB",
    "RUNNER_TEMP",
    "BAIOS_BOOT_SMOKE_ROOT",
    "BUSINESAIOS_PYTEST_BIN_DIR",
)


@dataclass(frozen=True)
class CommandOutcome:
    returncode: int
    stdout: str
    stderr: str


def _base_env() -> dict[str, str]:
    # Keep CI subprocesses hermetic. The execution environment can contain
    # platform-specific CUA_DD/Jupyter variables that make pytest children hang
    # at shutdown; do not leak them into project gates. Dynamic linker paths and
    # a narrowly-scoped GitHub runner context are intentionally preserved so
    # self-hosted jobs can use runner-local Python builds and job-scoped temp
    # directories without falling back to shared /tmp paths.
    env: dict[str, str] = {}
    for key in PRESERVED_ENV_KEYS:
        if key in os.environ:
            env[key] = os.environ[key]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["DD_TRACE_ENABLED"] = "0"
    env["DD_TRACE_STARTUP_LOGS"] = "0"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = str(repo_root())
    return env


def _merged_env(env: Mapping[str, str] | None = None, *, use_base_env: bool = True) -> dict[str, str]:
    merged_env = _base_env() if use_base_env else dict(os.environ)
    if env:
        merged_env.update({str(k): str(v) for k, v in env.items()})
    return merged_env


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    echo_output: bool = True,
) -> CommandOutcome:
    printable = " ".join(shlex.quote(part) for part in command)
    effective_timeout = DEFAULT_TIMEOUT_SECONDS if timeout is None else timeout
    print(f"[ci] run {printable} (timeout={effective_timeout}s)")
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd or repo_root()),
            env=_merged_env(env),
            text=True,
            capture_output=True,
            check=False,
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        message = f"TIMEOUT after {effective_timeout}s: {printable}\n{stderr}"
        print(message, file=sys.stderr)
        return CommandOutcome(returncode=124, stdout=stdout, stderr=message)
    if echo_output and completed.stdout:
        print(completed.stdout, end="")
    if echo_output and completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return CommandOutcome(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def stream_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    on_stdout_line: Callable[[str], None] | None = None,
    use_base_env: bool = True,
) -> int:
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd or repo_root()),
        env=_merged_env(env, use_base_env=use_base_env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        if on_stdout_line is not None:
            on_stdout_line(line)
        else:
            print(line, end="")
    return int(process.wait())


def run_python(args: Sequence[str], *, timeout: float | None = None) -> CommandOutcome:
    # -S prevents implicit sitecustomize/usercustomize boot during non-test CI subprocesses.
    return run_command([sys.executable, "-S", *args], timeout=timeout)


def _pytest_args_with_required_plugins(args: Sequence[str]) -> list[str]:
    output = list(args)
    existing_plugins = {
        output[index + 1]
        for index, item in enumerate(output[:-1])
        if item == "-p"
    }
    insertion_index = 2 if len(output) >= 2 and output[0] == "-m" and output[1] == "pytest" else 0
    plugin_args: list[str] = []
    for plugin in PYTEST_REQUIRED_PLUGINS:
        if plugin not in existing_plugins:
            plugin_args.extend(["-p", plugin])
    return [*output[:insertion_index], *plugin_args, *output[insertion_index:]]


def run_pytest(args: Sequence[str], *, timeout: float | None = None) -> CommandOutcome:
    # pytest lives in site-packages; -S hides it. Keep user-site/plugin autoload
    # disabled, but explicitly load project-required plugin entrypoints. This
    # prevents async tests from being silently skipped while still blocking
    # ambient plugins.
    args_with_plugins = _pytest_args_with_required_plugins(args)
    command: list[str]
    if len(args_with_plugins) >= 2 and args_with_plugins[0] == "-m" and args_with_plugins[1] == "pytest":
        wrapper = (
            "import os, sys; "
            "import pytest; "
            "code = pytest.main(sys.argv[1:]); "
            "sys.stdout.flush(); sys.stderr.flush(); "
            "os._exit(int(code))"
        )
        command = [sys.executable, "-c", wrapper, *args_with_plugins[2:]]
    else:
        command = [sys.executable, *args_with_plugins]
    return run_command(command, timeout=timeout)


__all__ = ["CommandOutcome", "run_command", "run_python", "run_pytest", "stream_command"]
