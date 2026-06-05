"""Compatibility runner for low-risk Ruff SIM cleanup.

Uses a conservative SIM subset on low-risk maintenance/test scopes only:
tools, scripts, tests.

Selected rules:
- SIM101: duplicate isinstance calls
- SIM102: collapsible nested if statements
- SIM103: return condition directly
- SIM118: use key in dict instead of key in dict.keys()

It does not select F401 and does not request unsafe fixes. The surrounding
server-local orchestrator runs the full gate before a branch is pushed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "ci" / "ruff_simple_factory"
SCOPES = ("tools", "scripts", "tests")
RULES = ("SIM101", "SIM102", "SIM103", "SIM118")


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(ROOT), check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def changed_files() -> list[str]:
    result = run(["git", "diff", "--name-only"])
    if result.returncode != 0:
        raise SystemExit(f"git diff failed: {result.stderr}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
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
    report = {
        "scopes": list(SCOPES),
        "rules": list(RULES),
        "forbidden_autofix_rules": ["F401"],
        "before": summary(before),
        "after": summary(after),
        "reduced": len(before) - len(after),
        "changed_files": changed_files(),
    }
    write(ARTIFACTS / "summary.json", json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
