from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.ci.config import project_shape_config


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifact_dir(root: Path) -> Path:
    path = root / "artifacts" / "ci" / "ruff_debt_reduction"
    path.mkdir(parents=True, exist_ok=True)
    return path


def quality_targets(root: Path) -> tuple[str, ...]:
    targets = project_shape_config(root).quality_targets
    if not targets:
        raise RuntimeError("quality_targets_missing")
    return tuple(str(root / target) for target in targets)


def run_command(argv: Sequence[str], *, cwd: Path) -> CommandResult:
    proc = subprocess.run(
        list(argv),
        cwd=str(cwd),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return CommandResult(tuple(argv), int(proc.returncode), proc.stdout, proc.stderr)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_ruff_json(result: CommandResult) -> list[dict[str, Any]]:
    raw = result.stdout.strip()
    if not raw:
        if result.returncode == 0:
            return []
        raise RuntimeError(
            "ruff_json_output_missing\n"
            f"command={' '.join(result.argv)}\n"
            f"returncode={result.returncode}\n"
            f"stderr={result.stderr.strip()}"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "ruff_json_output_parse_failed\n"
            f"command={' '.join(result.argv)}\n"
            f"returncode={result.returncode}\n"
            f"stderr={result.stderr.strip()}\n"
            f"error={exc}"
        ) from exc
    if not isinstance(parsed, list):
        raise RuntimeError("ruff_json_output_not_list")
    return [item for item in parsed if isinstance(item, dict)]


def ruff_json_report(*, root: Path, targets: Sequence[str], output_path: Path) -> list[dict[str, Any]]:
    result = run_command(
        [sys.executable, "-m", "ruff", "check", *targets, "--output-format", "json"],
        cwd=root,
    )
    write_text(output_path, result.stdout)
    if result.stderr.strip():
        write_text(output_path.with_suffix(".stderr.txt"), result.stderr)
    if result.returncode not in {0, 1}:
        raise RuntimeError(
            "ruff_json_report_failed\n"
            f"returncode={result.returncode}\n"
            f"stderr={result.stderr.strip()}"
        )
    return load_ruff_json(result)


def apply_safe_ruff_fixes(*, root: Path, targets: Sequence[str], artifact_root: Path) -> CommandResult:
    result = run_command([sys.executable, "-m", "ruff", "check", *targets, "--fix"], cwd=root)
    write_text(artifact_root / "safe_fix.stdout.txt", result.stdout)
    write_text(artifact_root / "safe_fix.stderr.txt", result.stderr)
    if result.returncode not in {0, 1}:
        raise RuntimeError(
            "ruff_safe_fix_failed\n"
            f"returncode={result.returncode}\n"
            f"stderr={result.stderr.strip()}"
        )
    return result


def summarize(findings: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(findings)
    by_code = Counter(str(item.get("code") or "UNKNOWN") for item in items)
    by_file = Counter(str(item.get("filename") or "UNKNOWN") for item in items)
    fixable = 0
    unsafe_fixable = 0
    for item in items:
        fix = item.get("fix")
        if not isinstance(fix, dict):
            continue
        applicability = str(fix.get("applicability") or "")
        if applicability == "safe":
            fixable += 1
        elif applicability:
            unsafe_fixable += 1
    return {
        "total": len(items),
        "fixable_safe": fixable,
        "fixable_unsafe_or_unknown": unsafe_fixable,
        "by_code": dict(by_code.most_common()),
        "top_files": dict(by_file.most_common(75)),
    }


def run_gate(*, root: Path, gate: str, strict_ruff: bool, artifact_root: Path) -> CommandResult:
    env_prefix = "BAIOS_REQUIRE_FULL_RUFF=1 " if strict_ruff else ""
    result = run_command([sys.executable, "-m", "scripts.ci.cli", "--gate", gate], cwd=root)
    write_text(artifact_root / f"gate_{gate}.stdout.txt", result.stdout)
    write_text(artifact_root / f"gate_{gate}.stderr.txt", result.stderr)
    if strict_ruff:
        write_text(artifact_root / f"gate_{gate}.command.txt", f"{env_prefix}{' '.join(result.argv)}\n")
    return result


def markdown_summary(*, before: dict[str, Any], after: dict[str, Any], gate: CommandResult | None) -> str:
    lines = [
        "# Ruff debt reduction report",
        "",
        f"Before total: {before['total']}",
        f"After total: {after['total']}",
        f"Reduced: {int(before['total']) - int(after['total'])}",
        f"Safe fixable before: {before['fixable_safe']}",
        f"Safe fixable after: {after['fixable_safe']}",
        "",
        "## Remaining by code",
    ]
    for code, count in dict(after["by_code"]).items():
        lines.append(f"- {code}: {count}")
    lines.extend(["", "## Remaining top files"])
    for filename, count in dict(after["top_files"]).items():
        lines.append(f"- {count}: {filename}")
    if gate is not None:
        lines.extend(
            [
                "",
                "## Gate",
                f"Command: `{' '.join(gate.argv)}`",
                f"Return code: {gate.returncode}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlled safe Ruff debt reduction runner.")
    parser.add_argument("--apply-safe-fixes", action="store_true", help="Apply Ruff safe fixes only. Unsafe fixes are never enabled.")
    parser.add_argument("--gate", default="business-critical", help="CI gate to run after reporting/fixing.")
    parser.add_argument("--skip-gate", action="store_true", help="Do not run a CI gate after debt reporting/fixing.")
    parser.add_argument("--strict-gate-ruff", action="store_true", help="Document that the post-fix gate should be interpreted as strict-Ruff work.")
    parser.add_argument("--require-clean", action="store_true", help="Exit non-zero if any Ruff debt remains after fixes.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = repo_root()
    artifacts = artifact_dir(root)
    targets = quality_targets(root)

    before_items = ruff_json_report(root=root, targets=targets, output_path=artifacts / "ruff_before.json")
    before = summarize(before_items)

    if args.apply_safe_fixes:
        apply_safe_ruff_fixes(root=root, targets=targets, artifact_root=artifacts)

    after_items = ruff_json_report(root=root, targets=targets, output_path=artifacts / "ruff_after.json")
    after = summarize(after_items)

    gate_result = None
    if not args.skip_gate:
        gate_result = run_gate(root=root, gate=str(args.gate), strict_ruff=bool(args.strict_gate_ruff), artifact_root=artifacts)

    summary = {
        "artifact": "ruff_debt_reduction",
        "safe_fixes_applied": bool(args.apply_safe_fixes),
        "unsafe_fixes_applied": False,
        "before": before,
        "after": after,
        "reduced_total": int(before["total"]) - int(after["total"]),
        "gate": None
        if gate_result is None
        else {
            "argv": list(gate_result.argv),
            "returncode": gate_result.returncode,
        },
    }
    write_text(artifacts / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write_text(artifacts / "summary.md", markdown_summary(before=before, after=after, gate=gate_result))

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    if args.require_clean and int(after["total"]) != 0:
        return 2
    if gate_result is not None and gate_result.returncode != 0:
        return gate_result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
