"""Guarded Ruff debt reduction factory.

This tool exists to reduce Ruff debt in large batches without deleting public API
or changing runtime semantics by accident.

Rules:
- never auto-fix F401;
- never enable unsafe fixes;
- run a gate after the patch;
- rollback the working tree if the gate fails when --rollback-on-fail is set;
- write before/after reports and changed-file summaries.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ci" / "ruff_debt_factory"

SAFE_RULE_PROFILES: dict[str, tuple[str, ...]] = {
    "typing": ("UP006", "UP007", "UP035", "UP037", "UP045"),
    "imports": ("I001",),
    "simple": ("SIM101", "SIM102", "SIM103", "SIM105", "SIM110", "SIM117", "SIM118"),
    "bugbear-safe": ("B007", "B009", "B010", "B013", "B014", "B023", "B026", "B904"),
}

FORBIDDEN_AUTOFIX_RULES = frozenset({"F401"})
DEFAULT_SCOPE = ("tools", "scripts", "tests")


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def _emit(message: str) -> None:
    sys.stdout.write(message + "\n")


def _run(argv: list[str], *, cwd: Path = REPO_ROOT) -> CommandResult:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return CommandResult(tuple(argv), int(proc.returncode), proc.stdout, proc.stderr)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git_clean_status() -> bool:
    status = _run(["git", "status", "--short"])
    return status.returncode == 0 and not status.stdout.strip()


def _git_head() -> str:
    result = _run(["git", "rev-parse", "HEAD"])
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git rev-parse failed")
    return result.stdout.strip()


def _git_changed_files() -> list[str]:
    result = _run(["git", "diff", "--name-only"])
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git diff failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_reset_hard() -> None:
    result = _run(["git", "reset", "--hard"])
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git reset --hard failed")


def _load_ruff_json(result: CommandResult) -> list[dict[str, Any]]:
    raw = result.stdout.strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise SystemExit("ruff json output is not a list")
    return [item for item in parsed if isinstance(item, dict)]


def _ruff_report(*, scopes: tuple[str, ...], artifact_dir: Path, label: str) -> list[dict[str, Any]]:
    result = _run([sys.executable, "-m", "ruff", "check", *scopes, "--output-format", "json"])
    _write(artifact_dir / f"ruff_{label}.json", result.stdout)
    _write(artifact_dir / f"ruff_{label}.stderr.txt", result.stderr)
    if result.returncode not in {0, 1}:
        raise SystemExit(f"ruff report failed: {result.returncode}\n{result.stderr}")
    return _load_ruff_json(result)


def _summarize(findings: list[dict[str, Any]]) -> dict[str, Any]:
    by_code = Counter(str(item.get("code") or "UNKNOWN") for item in findings)
    by_file = Counter(str(item.get("filename") or "UNKNOWN") for item in findings)
    return {
        "total": len(findings),
        "by_code": dict(by_code.most_common()),
        "top_files": dict(by_file.most_common(100)),
    }


def _selected_rules(profiles: tuple[str, ...], explicit_rules: tuple[str, ...]) -> tuple[str, ...]:
    selected: list[str] = []
    for profile in profiles:
        rules = SAFE_RULE_PROFILES.get(profile)
        if rules is None:
            raise SystemExit(f"unknown profile: {profile}; known={sorted(SAFE_RULE_PROFILES)}")
        selected.extend(rules)
    selected.extend(explicit_rules)
    forbidden = sorted(set(selected) & FORBIDDEN_AUTOFIX_RULES)
    if forbidden:
        raise SystemExit(f"forbidden autofix rule requested: {forbidden}")
    return tuple(dict.fromkeys(selected))


def _apply_ruff_fix(*, scopes: tuple[str, ...], rules: tuple[str, ...], artifact_dir: Path) -> CommandResult:
    if not rules:
        raise SystemExit("no rules selected")
    result = _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            *scopes,
            "--fix",
            "--select",
            ",".join(rules),
            "--ignore",
            ",".join(sorted(FORBIDDEN_AUTOFIX_RULES)),
        ]
    )
    _write(artifact_dir / "ruff_fix.stdout.txt", result.stdout)
    _write(artifact_dir / "ruff_fix.stderr.txt", result.stderr)
    if result.returncode not in {0, 1}:
        raise SystemExit(f"ruff fix failed: {result.returncode}\n{result.stderr}")
    return result


def _run_gate(gate: str, artifact_dir: Path) -> CommandResult:
    result = _run([sys.executable, "-m", "scripts.ci.cli", "--gate", gate])
    _write(artifact_dir / f"gate_{gate}.stdout.txt", result.stdout)
    _write(artifact_dir / f"gate_{gate}.stderr.txt", result.stderr)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded Ruff debt reduction factory.")
    parser.add_argument("--scope", action="append", default=[], help="Scope path. Repeatable. Default: tools,scripts,tests")
    parser.add_argument("--profile", action="append", default=[], help=f"Safe profile. Known: {', '.join(sorted(SAFE_RULE_PROFILES))}")
    parser.add_argument("--rule", action="append", default=[], help="Explicit allowlisted Ruff rule to fix. F401 is forbidden.")
    parser.add_argument("--gate", default="full", help="CI gate to run after patch. Default: full")
    parser.add_argument("--apply", action="store_true", help="Apply fixes. Without this, only report.")
    parser.add_argument("--rollback-on-fail", action="store_true", help="Rollback working tree if the post-fix gate fails.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow running with a dirty working tree.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.allow_dirty and not _git_clean_status():
        raise SystemExit("working tree is dirty; commit/stash/reset before running or pass --allow-dirty")

    scopes = tuple(args.scope or DEFAULT_SCOPE)
    profiles = tuple(args.profile or ("typing",))
    rules = _selected_rules(profiles, tuple(args.rule or ()))

    run_id = _git_head()[:12]
    artifact_dir = ARTIFACT_ROOT / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    before = _ruff_report(scopes=scopes, artifact_dir=artifact_dir, label="before")
    gate_result: CommandResult | None = None

    if args.apply:
        _apply_ruff_fix(scopes=scopes, rules=rules, artifact_dir=artifact_dir)
        after = _ruff_report(scopes=scopes, artifact_dir=artifact_dir, label="after")
        changed_files = _git_changed_files()
        _write(artifact_dir / "changed_files.txt", "\n".join(changed_files) + ("\n" if changed_files else ""))
        gate_result = _run_gate(str(args.gate), artifact_dir)
        if gate_result.returncode != 0 and args.rollback_on_fail:
            _git_reset_hard()
    else:
        after = before
        changed_files = []

    summary = {
        "scopes": list(scopes),
        "profiles": list(profiles),
        "rules": list(rules),
        "forbidden_autofix_rules": sorted(FORBIDDEN_AUTOFIX_RULES),
        "applied": bool(args.apply),
        "rollback_on_fail": bool(args.rollback_on_fail),
        "before": _summarize(before),
        "after": _summarize(after),
        "reduced": len(before) - len(after),
        "changed_files": changed_files,
        "gate": None if gate_result is None else {"argv": list(gate_result.argv), "returncode": gate_result.returncode},
        "rolled_back": bool(gate_result is not None and gate_result.returncode != 0 and args.rollback_on_fail),
    }
    _write(artifact_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _emit(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if gate_result is not None and gate_result.returncode != 0:
        return gate_result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
