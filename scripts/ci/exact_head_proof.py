"""Billing-independent exact-head proof for canonical CI gates.

This runner does not duplicate CI plans. It proves a clean Git commit and then
invokes the existing ``scripts.ci.cli`` gates with the current Python
interpreter. Run it once under Python 3.11 and once under Python 3.12 to mirror
the hosted matrix while GitHub-hosted Actions are unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.ci.plan_registry import allowed_gates

CANON_EXACT_HEAD_PROOF = True
EXACT_HEAD_PROOF_SCHEMA_VERSION = 2
DEFAULT_TIMEOUT_SECONDS = 3 * 60 * 60
HOSTED_EQUIVALENT_GATES = (
    "business-critical",
    "fast",
    "targeted-domain",
    "full",
)


class ExactHeadProofError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: tuple[str, ...]
    returncode: int
    duration_ms: int
    timed_out: bool = False
    smoke_root: str = ""

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out


@dataclass(frozen=True)
class ProofReport:
    schema_version: int
    success: bool
    head_sha: str
    expected_sha: str
    target_base: str
    target_base_sha: str
    repository: str
    python_executable: str
    python_version: str
    platform: str
    timeout_seconds: int
    smoke_parent: str
    started_at: str
    finished_at: str
    commands: tuple[CommandResult, ...]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _git_text(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "git failed").strip()
        raise ExactHeadProofError(detail)
    return (completed.stdout or "").strip()


def resolve_head_sha(repo: Path) -> str:
    value = _git_text(repo, "rev-parse", "HEAD")
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise ExactHeadProofError(f"invalid HEAD SHA: {value!r}")
    return value


def require_clean_worktree(repo: Path) -> None:
    status = _git_text(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        sample = " | ".join(status.splitlines()[:12])
        raise ExactHeadProofError(f"worktree is not clean: {sample}")


def resolve_target_base_sha(repo: Path, target_base: str) -> str:
    value = _git_text(
        repo,
        "rev-parse",
        "--verify",
        f"{target_base}^{{commit}}",
    )
    if len(value) != 40:
        raise ExactHeadProofError(
            f"target base does not resolve to a commit: {target_base}"
        )
    return value


def _run_command(
    *,
    name: str,
    command: Sequence[str],
    repo: Path,
    env: dict[str, str],
    timeout_seconds: int,
    smoke_root: str = "",
) -> CommandResult:
    started = time.monotonic_ns()
    timed_out = False
    try:
        completed = subprocess.run(
            list(command),
            cwd=repo,
            env=env,
            check=False,
            timeout=timeout_seconds,
        )
        returncode = int(completed.returncode)
    except subprocess.TimeoutExpired:
        timed_out = True
        returncode = 124
    duration_ms = int((time.monotonic_ns() - started) / 1_000_000)
    return CommandResult(
        name=name,
        command=tuple(command),
        returncode=returncode,
        duration_ms=duration_ms,
        timed_out=timed_out,
        smoke_root=smoke_root,
    )


def _write_report(path: Path, report: ProofReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(report)
    payload["commands"] = [asdict(item) for item in report.commands]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _gate_smoke_root(
    *,
    smoke_parent: Path,
    index: int,
    gate: str,
) -> Path:
    safe_gate = "".join(
        character if character.isalnum() else "-"
        for character in gate.casefold()
    ).strip("-")
    return smoke_parent / f"{index:02d}-{safe_gate}"


def _proof_base_env(*, target_base: str) -> dict[str, str]:
    """Return a clean proof environment shared by non-gate commands.

    A hosted workflow may already define ``BAIOS_BOOT_SMOKE_ROOT`` for its own
    outer gate. Exact-head proof creates a separate root per nested gate, so the
    inherited value must never leak into dependency-lock or another gate.
    """

    env = dict(os.environ)
    env.pop("BAIOS_BOOT_SMOKE_ROOT", None)
    env["TARGETED_CI_BASE"] = target_base
    return env


def run_exact_head_proof(
    *,
    repo: Path,
    expected_sha: str,
    gates: Sequence[str] = HOSTED_EQUIVALENT_GATES,
    target_base: str = "origin/main",
    report_path: Path | None = None,
    fail_fast: bool = False,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProofReport:
    root = repo.resolve()
    expected = str(expected_sha or "").strip().lower()
    if len(expected) != 40:
        raise ExactHeadProofError(
            "--expected-sha must be a full 40-character SHA"
        )
    if int(timeout_seconds) <= 0:
        raise ExactHeadProofError("--timeout-seconds must be positive")

    unknown = tuple(gate for gate in gates if gate not in allowed_gates())
    if unknown:
        raise ExactHeadProofError(f"unknown gate(s): {', '.join(unknown)}")

    require_clean_worktree(root)
    head_sha = resolve_head_sha(root)
    if head_sha != expected:
        raise ExactHeadProofError(
            f"HEAD mismatch: expected {expected}, actual {head_sha}"
        )

    target_base_sha = resolve_target_base_sha(root, target_base)
    started_at = _utc_now()
    commands: list[CommandResult] = []
    base_env = _proof_base_env(target_base=target_base)

    smoke_parent = Path(
        tempfile.mkdtemp(prefix=f"businesaios-proof-{head_sha[:12]}-")
    )

    lock_result = _run_command(
        name="requirements-lock",
        command=(sys.executable, "scripts/ci/check_requirements_lock.py"),
        repo=root,
        env=base_env,
        timeout_seconds=timeout_seconds,
    )
    commands.append(lock_result)

    if lock_result.success or not fail_fast:
        for index, gate in enumerate(gates, start=1):
            smoke_root = _gate_smoke_root(
                smoke_parent=smoke_parent,
                index=index,
                gate=gate,
            )
            gate_env = dict(base_env)
            gate_env["BAIOS_BOOT_SMOKE_ROOT"] = str(smoke_root)
            result = _run_command(
                name=gate,
                command=(
                    sys.executable,
                    "-m",
                    "scripts.ci.cli",
                    "--gate",
                    gate,
                ),
                repo=root,
                env=gate_env,
                timeout_seconds=timeout_seconds,
                smoke_root=str(smoke_root),
            )
            commands.append(result)
            if fail_fast and not result.success:
                break

    success = bool(commands) and all(item.success for item in commands)
    report = ProofReport(
        schema_version=EXACT_HEAD_PROOF_SCHEMA_VERSION,
        success=success,
        head_sha=head_sha,
        expected_sha=expected,
        target_base=target_base,
        target_base_sha=target_base_sha,
        repository=str(root),
        python_executable=sys.executable,
        python_version=platform.python_version(),
        platform=platform.platform(),
        timeout_seconds=int(timeout_seconds),
        smoke_parent=str(smoke_parent),
        started_at=started_at,
        finished_at=_utc_now(),
        commands=tuple(commands),
    )
    if report_path is None:
        output = root / "artifacts" / "ci" / "exact_head_proof.json"
    elif report_path.is_absolute():
        output = report_path
    else:
        output = root / report_path
    _write_report(output, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument(
        "--gate",
        action="append",
        dest="gates",
        choices=allowed_gates(),
        help="Repeat to override the hosted-equivalent gate set.",
    )
    parser.add_argument("--target-base", default="origin/main")
    parser.add_argument(
        "--report",
        default="artifacts/ci/exact_head_proof.json",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--fail-fast", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = run_exact_head_proof(
            repo=Path(args.repo),
            expected_sha=args.expected_sha,
            gates=tuple(args.gates or HOSTED_EQUIVALENT_GATES),
            target_base=args.target_base,
            report_path=Path(args.report),
            fail_fast=bool(args.fail_fast),
            timeout_seconds=int(args.timeout_seconds),
        )
    except ExactHeadProofError as exc:
        print(
            f"[exact-head-proof] failed before gates: {exc}",
            file=sys.stderr,
        )
        return 2

    for result in report.commands:
        print(
            f"[exact-head-proof] step={result.name} "
            f"success={result.success} timed_out={result.timed_out} "
            f"duration_ms={result.duration_ms}"
        )
    print(f"[exact-head-proof] head={report.head_sha}")
    print(f"[exact-head-proof] success={report.success}")
    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
