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

ARTIFACTS = ROOT / "artifacts" / "ci" / "ruff_debt_reduction_no_f401"

# This runner intentionally matches the canonical full debt command:
#     python -m ruff check .
#
# F401 is intentionally excluded from auto-fix. In this repository many imports
# are public API re-exports in __init__.py, *_surface.py, base.py and canonical
# compatibility modules. Removing them can break runtime boot while looking like
# a harmless style cleanup.
AUTO_FIX_SELECT = "E,I,UP,SIM,B007,B009,B010,B013,B014,B023,B026,B904"
AUTO_FIX_IGNORE = "F401"
TARGETS = ["."]


@dataclass(frozen=True)
class RunnerResult:
    returncode: int
    stdout: str
    stderr: str


def _run(argv: list[str]) -> RunnerResult:
    result = ci_run_command(argv, cwd=ROOT, echo_output=False)
    return RunnerResult(returncode=int(result.returncode), stdout=result.stdout, stderr=result.stderr)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ruff_json(name: str) -> list[dict[str, Any]]:
    proc = _run([sys.executable, "-m", "ruff", "check", *TARGETS, "--output-format", "json"])
    _write(ARTIFACTS / f"{name}.json", proc.stdout)
    _write(ARTIFACTS / f"{name}.stderr.txt", proc.stderr)
    if proc.returncode not in {0, 1}:
        raise SystemExit(f"ruff report failed: {proc.returncode}\n{proc.stderr}")
    raw = proc.stdout.strip()
    return json.loads(raw) if raw else []


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(items),
        "by_code": dict(Counter(str(item.get("code") or "UNKNOWN") for item in items).most_common()),
        "top_files": dict(Counter(str(item.get("filename") or "UNKNOWN") for item in items).most_common(75)),
    }


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    before = _ruff_json("before")

    fix = _run([
        sys.executable,
        "-m",
        "ruff",
        "check",
        *TARGETS,
        "--fix",
        "--select",
        AUTO_FIX_SELECT,
        "--ignore",
        AUTO_FIX_IGNORE,
    ])
    _write(ARTIFACTS / "fix.stdout.txt", fix.stdout)
    _write(ARTIFACTS / "fix.stderr.txt", fix.stderr)
    if fix.returncode not in {0, 1}:
        raise SystemExit(f"ruff fix failed: {fix.returncode}\n{fix.stderr}")

    after = _ruff_json("after")
    gate = _run([sys.executable, "-m", "scripts.ci.cli", "--gate", "full"])
    _write(ARTIFACTS / "gate_full.stdout.txt", gate.stdout)
    _write(ARTIFACTS / "gate_full.stderr.txt", gate.stderr)

    report = {
        "debt_command": "python -m ruff check .",
        "autofix_command": f"python -m ruff check . --fix --select {AUTO_FIX_SELECT} --ignore {AUTO_FIX_IGNORE}",
        "autofix_select": AUTO_FIX_SELECT,
        "autofix_ignore": AUTO_FIX_IGNORE,
        "f401_autofix_applied": False,
        "before": _summary(before),
        "after": _summary(after),
        "reduced_total": len(before) - len(after),
        "gate_full_returncode": gate.returncode,
    }
    _write(ARTIFACTS / "summary.json", json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return gate.returncode


if __name__ == "__main__":
    raise SystemExit(main())
