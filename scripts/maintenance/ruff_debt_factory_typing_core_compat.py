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

ARTIFACTS = ROOT / "artifacts" / "ci" / "ruff_typing_core_factory"
SCOPES = ("application", "core", "interfaces", "services")
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


def existing_scopes() -> tuple[str, ...]:
    return tuple(scope for scope in SCOPES if (ROOT / scope).exists())


def ruff_report(label: str) -> list[dict[str, Any]]:
    scopes = existing_scopes()
    result = run([sys.executable, "-m", "ruff", "check", *scopes, "--output-format", "json"])
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
    scopes = existing_scopes()
    if not scopes:
        return 0
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    before = ruff_report("before")
    fix = run([
        sys.executable,
        "-m",
        "ruff",
        "check",
        *scopes,
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
        "scopes": list(scopes),
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
