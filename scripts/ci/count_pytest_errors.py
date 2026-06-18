from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PytestErrorCountReport:
    total: int
    passed: int
    failures: int
    errors: int
    skipped: int
    failed_items: tuple[str, ...]
    error_items: tuple[str, ...]
    exit_code: int

    @property
    def problem_count(self) -> int:
        return self.failures + self.errors

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and self.problem_count == 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pytest and count failures/errors from JUnit XML.")
    parser.add_argument("--json", dest="json_path", default="", help="Optional path for JSON report.")
    parser.add_argument("--quiet-output", action="store_true", help="Do not stream pytest stdout/stderr.")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Arguments passed to pytest after --.")
    return parser


def _clean_pytest_args(raw_args: list[str]) -> list[str]:
    args = list(raw_args)
    if args and args[0] == "--":
        args = args[1:]
    return args or ["-q", "--import-mode=importlib", "--tb=short", "tests"]


def _case_name(case: ET.Element) -> str:
    classname = str(case.attrib.get("classname") or "").strip()
    name = str(case.attrib.get("name") or "").strip()
    return "::".join(part for part in (classname, name) if part) or "<unknown>"


def _parse_junit(path: Path, *, exit_code: int) -> PytestErrorCountReport:
    if not path.exists():
        return PytestErrorCountReport(0, 0, 0, 0, 0, (), ("junit xml was not created",), exit_code)
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    failed_items: list[str] = []
    error_items: list[str] = []
    skipped = 0
    for case in cases:
        name = _case_name(case)
        if case.find("failure") is not None:
            failed_items.append(name)
        if case.find("error") is not None:
            error_items.append(name)
        if case.find("skipped") is not None:
            skipped += 1
    failures = len(failed_items)
    errors = len(error_items)
    total = len(cases)
    passed = max(total - failures - errors - skipped, 0)
    return PytestErrorCountReport(
        total=total,
        passed=passed,
        failures=failures,
        errors=errors,
        skipped=skipped,
        failed_items=tuple(failed_items),
        error_items=tuple(error_items),
        exit_code=exit_code,
    )


def _write_json(path: str, report: PytestErrorCountReport) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(report) | {"problem_count": report.problem_count, "success": report.success}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _pytest_env() -> dict[str, str]:
    tmp_root = Path(tempfile.gettempdir())
    env = dict(os.environ)
    env.setdefault("CARGO_TARGET_DIR", str(tmp_root / "businesaios-cargo-target"))
    env.setdefault("DATA_DIR", str(tmp_root / "businesaios-pytest-data"))
    env.setdefault("BUSINESAIOS_HOME", str(tmp_root / "businesaios-pytest-home"))
    return env


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pytest_args = _clean_pytest_args(args.pytest_args)
    with tempfile.TemporaryDirectory(prefix="pytest-error-count-") as tmp:
        junit_path = Path(tmp) / "pytest-junit.xml"
        command = [sys.executable, "-m", "pytest", *pytest_args, f"--junitxml={junit_path}"]
        completed = subprocess.run(command, text=True, capture_output=args.quiet_output, check=False, env=_pytest_env())
        if args.quiet_output:
            if completed.stdout:
                sys.stdout.write(completed.stdout)
            if completed.stderr:
                sys.stderr.write(completed.stderr)
        report = _parse_junit(junit_path, exit_code=int(completed.returncode))
    print(
        "[pytest-count] "
        f"total={report.total} passed={report.passed} failures={report.failures} "
        f"errors={report.errors} skipped={report.skipped} problems={report.problem_count}"
    )
    if report.failed_items:
        print("[pytest-count] failed:")
        for item in report.failed_items:
            print(f"  - {item}")
    if report.error_items:
        print("[pytest-count] errors:")
        for item in report.error_items:
            print(f"  - {item}")
    if args.json_path:
        _write_json(args.json_path, report)
        print(f"[pytest-count] json={args.json_path}")
    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
