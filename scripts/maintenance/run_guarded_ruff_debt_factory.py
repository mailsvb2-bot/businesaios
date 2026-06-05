"""Server-local orchestrator for guarded Ruff debt reduction.

This runner is intended for the project's own server, not GitHub Actions.
It keeps the workflow local and cost-free:

1. requires a clean or cleanup-only working tree;
2. creates a dedicated debt branch;
3. runs a guarded factory profile;
4. runs the full CI gate;
5. commits and pushes only when the full gate is green;
6. creates/updates a PR with `gh` only when GitHub CLI is authenticated.

It does not enable unsafe Ruff fixes and relies on the guarded factory profile
for preserving public API surfaces, including the F401 no-autofix rule.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "ci" / "server_ruff_debt_factory"
RUNTIME_ARTIFACT_PATHS = (
    "data/business_autonomy",
    "runtime/data/security",
    "rust/businessaios_safety_core/target",
    "security/process_owner_security_audit.jsonl",
)


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def emit(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


def run(argv: Sequence[str], *, check: bool = False) -> CommandResult:
    proc = subprocess.run(
        list(argv),
        cwd=str(REPO_ROOT),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = CommandResult(tuple(str(item) for item in argv), int(proc.returncode), proc.stdout, proc.stderr)
    if check and result.returncode != 0:
        raise SystemExit(
            "command failed\n"
            f"argv={' '.join(result.argv)}\n"
            f"returncode={result.returncode}\n"
            f"stdout={result.stdout[-4000:]}\n"
            f"stderr={result.stderr[-4000:]}"
        )
    return result


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def git_status_short() -> str:
    return run(["git", "status", "--short"], check=True).stdout


def clean_runtime_artifacts() -> None:
    for rel in RUNTIME_ARTIFACT_PATHS:
        path = REPO_ROOT / rel
        if path.exists():
            run(["git", "clean", "-fd", rel], check=True)


def ensure_clean_tree() -> None:
    status = git_status_short().strip()
    if status:
        raise SystemExit("working tree is dirty after cleanup; refusing to continue:\n" + status)


def current_branch() -> str:
    return run(["git", "branch", "--show-current"], check=True).stdout.strip()


def current_head() -> str:
    return run(["git", "rev-parse", "HEAD"], check=True).stdout.strip()


def changed_files() -> list[str]:
    output = run(["git", "diff", "--name-only"], check=True).stdout
    return [line.strip() for line in output.splitlines() if line.strip()]


def ruff_full_report(path: Path) -> None:
    result = run([sys.executable, "-m", "ruff", "check", "."])
    write(path, result.stdout + result.stderr)


def full_gate(path_stdout: Path, path_stderr: Path) -> CommandResult:
    result = run([sys.executable, "-m", "scripts.ci.cli", "--gate", "full"])
    write(path_stdout, result.stdout)
    write(path_stderr, result.stderr)
    return result


def run_factory(profile: str) -> None:
    if profile != "typing-compat":
        raise SystemExit(f"unsupported profile: {profile}")
    result = run([sys.executable, "-m", "scripts.maintenance.ruff_debt_factory_typing_compat"])
    write(ARTIFACT_DIR / "factory.stdout.txt", result.stdout)
    write(ARTIFACT_DIR / "factory.stderr.txt", result.stderr)
    if result.returncode != 0:
        raise SystemExit(
            "factory failed\n"
            f"returncode={result.returncode}\n"
            f"stdout={result.stdout[-4000:]}\n"
            f"stderr={result.stderr[-4000:]}"
        )


def gh_authenticated() -> bool:
    result = run(["gh", "auth", "status"])
    return result.returncode == 0


def create_or_update_pr(branch_name: str, base_branch: str, title: str, body_path: Path) -> None:
    if not gh_authenticated():
        emit("gh is not authenticated; skipped PR creation. Branch was pushed.")
        return
    existing = run([
        "gh",
        "pr",
        "list",
        "--head",
        branch_name,
        "--base",
        base_branch,
        "--json",
        "number",
        "--jq",
        ".[0].number // empty",
    ])
    number = existing.stdout.strip()
    if number:
        run(["gh", "pr", "edit", number, "--title", title, "--body-file", str(body_path)], check=True)
        emit(f"updated PR #{number}")
    else:
        run(["gh", "pr", "create", "--base", base_branch, "--head", branch_name, "--title", title, "--body-file", str(body_path)], check=True)
        emit("created PR")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run guarded Ruff debt factory locally on the server.")
    parser.add_argument("--profile", default="typing-compat", choices=("typing-compat",))
    parser.add_argument("--base", default="main")
    parser.add_argument("--branch", default="", help="Debt branch. Default: debt/ruff-typing-compat/<timestamp>")
    parser.add_argument("--no-push", action="store_true", help="Do not push branch even if gate is green.")
    parser.add_argument("--no-pr", action="store_true", help="Do not create/update PR even if gh is authenticated.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    branch_name = args.branch or f"debt/ruff-typing-compat/{timestamp()}"
    base_branch = str(args.base)

    emit("[server-factory] fetching base branch")
    run(["git", "fetch", "origin", base_branch], check=True)
    run(["git", "switch", base_branch], check=True)
    run(["git", "pull", "--ff-only", "origin", base_branch], check=True)
    clean_runtime_artifacts()
    ensure_clean_tree()

    base_sha = current_head()
    write(ARTIFACT_DIR / "base_sha.txt", base_sha + "\n")
    ruff_full_report(ARTIFACT_DIR / "ruff_before.txt")

    emit(f"[server-factory] creating branch {branch_name}")
    run(["git", "switch", "-C", branch_name], check=True)

    emit(f"[server-factory] running guarded factory profile={args.profile}")
    run_factory(str(args.profile))
    files = changed_files()
    write(ARTIFACT_DIR / "changed_files.txt", "\n".join(files) + ("\n" if files else ""))

    if not files:
        emit("[server-factory] no changes produced")
        return 0

    emit("[server-factory] running full gate")
    gate = full_gate(ARTIFACT_DIR / "full_gate.stdout.txt", ARTIFACT_DIR / "full_gate.stderr.txt")
    if gate.returncode != 0:
        emit("[server-factory] full gate failed; resetting branch")
        run(["git", "reset", "--hard", base_sha], check=True)
        return gate.returncode

    ruff_full_report(ARTIFACT_DIR / "ruff_after.txt")
    clean_runtime_artifacts()

    run(["git", "add", "-A"], check=True)
    run(["git", "commit", "-m", "chore: reduce Ruff typing debt via guarded factory"], check=True)
    head_sha = current_head()

    summary = {
        "profile": args.profile,
        "base_branch": base_branch,
        "branch": branch_name,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed_files": files,
        "full_gate_returncode": gate.returncode,
    }
    write(ARTIFACT_DIR / "server_factory_summary.json", json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    if not args.no_push:
        emit(f"[server-factory] pushing branch {branch_name}")
        run(["git", "push", "--force-with-lease", "origin", branch_name], check=True)

    if not args.no_pr:
        body_path = ARTIFACT_DIR / "pr_body.md"
        write(
            body_path,
            "## Guarded server-local Ruff debt factory\n\n"
            f"Profile: `{args.profile}`\n\n"
            "Safety constraints:\n"
            "- full gate passed before commit/push\n"
            "- unsafe Ruff fixes disabled\n"
            "- F401 autofix disabled by guarded factory\n"
            "- public API export contract remains in place\n\n"
            f"Base SHA: `{base_sha}`\n"
            f"Head SHA: `{head_sha}`\n"
            f"Changed files: `{len(files)}`\n",
        )
        create_or_update_pr(branch_name, base_branch, "chore: reduce Ruff typing debt via guarded factory", body_path)

    emit("[server-factory] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
