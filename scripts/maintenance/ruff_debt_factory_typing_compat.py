"""Compatibility runner for safe typing-related Ruff cleanup.

Uses only rules supported by the currently locked Ruff version:
UP006, UP007, UP035, UP037.

It does not select F401 and does not request unsafe fixes.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.subprocess_io import run_command as ci_run_command

ARTIFACTS = ROOT / "artifacts" / "ci" / "ruff_typing_factory"
SCOPES = ("tools", "scripts", "tests")
RULES = ("UP006", "UP007", "UP035", "UP037")


@dataclass(frozen=True)
class RunnerResult:
    returncode: int
    stdout: str
    stderr: str


def run(argv: list[str]) -> RunnerResult:
    result = ci_run_command(argv, cwd=ROOT, echo_output=False)
    return RunnerResult(returncode=int(result.returncode), stdout=result.stdout, stderr=result.stderr)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def status_clean() -> bool:
    result = run(["git", "status", "--short"])
    return result.returncode == 0 and not result.stdout.strip()


def changed_files() -> list[str]:
    result = run(["git", "diff", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def ruff_report(label: str) -> list[dict[str, Any]]:
    result = run([sys.executable, "-m", "ruff", "check", *SCOPES, "--output-format", "json"])
    write(ARTIFACTS / f"ruff_{label}.json", result.stdout)
    write(ARTIFACTS / f"ruff_{label}.stderr.txt", result.stderr)
    if result.returncode not in {0, 1}:
        raise SystemExit(f"ruff report failed: {result.returncode}\n{result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else []


def summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(items),
        "by_code": dict(Counter(str(item.get("code") or "UNKNOWN") for item in items).most_common()),
        "top_files": dict(Counter(str(item.get("filename") or "UNKNOWN") for item in items).most_common(80)),
    }


def main() -> int:
    if not status_clean():
        raise SystemExit("working tree is dirty; clean runtime artifacts before running")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    before = ruff_report("before")
    fix = run([
        sys.executable,
        "-m",
        "ruff",
        "check",
        *SCOPES,
        "--fix",
        "--select",
        ",".join(RULES),
        "--ignore",
        "F401",
    ])
    write(ARTIFACTS / "fix.stdout.txt", fix.stdout)
    write(ARTIFACTS / "fix.stderr.txt", fix.stderr)
    if fix.returncode not in {0, 1}:
        raise SystemExit(f"ruff fix failed: {fix.returncode}\n{fix.stderr}")
    after = ruff_report("after")
    gate = run([sys.executable, "-m", "scripts.ci.cli", "--gate", "full"])
    write(ARTIFACTS / "gate_full.stdout.txt", gate.stdout)
    write(ARTIFACTS / "gate_full.stderr.txt", gate.stderr)
    report = {
        "scopes": list(SCOPES),
        "rules": list(RULES),
        "forbidden_autofix_rules": ["F401"],
        "before": summary(before),
        "after": summary(after),
        "reduced": len(before) - len(after),
        "changed_files": changed_files(),
        "gate_full_returncode": gate.returncode,
    }
    write(ARTIFACTS / "summary.json", json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if gate.returncode != 0:
        run(["git", "reset", "--hard"])
        return gate.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
