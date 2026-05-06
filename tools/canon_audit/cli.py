from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.canon_audit.checks import run_canon_checks, run_operational_canon_checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BusinesAIOS Canon audit.")
    parser.add_argument("project_root", type=Path, help="Path to repository root.")
    parser.add_argument(
        "--scope",
        choices=["operational", "full"],
        default="operational",
        help="Audit scope. 'operational' audits the Canon enforcement surface; 'full' audits the whole repository.",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Optional path for a machine-readable report.")
    args = parser.parse_args()

    report = run_operational_canon_checks(args.project_root) if args.scope == "operational" else run_canon_checks(args.project_root)
    print(f"Scope: {args.scope}")
    print(f"Raw score: {report.raw_score_100}")
    print(f"Admission score: {report.admission_score_100}")
    print(f"Passed: {report.passed}")
    print("\nHard gates:")
    for gate in report.hard_gates:
        print(f"- [{'OK' if gate.passed else 'FAIL'}] {gate.gate_name}: {gate.message}")
    if report.violations:
        print("\nViolations:")
        for violation in report.violations:
            print(f"- [{violation.code}] {violation.subject}: {violation.message}")

    if args.json_out is not None:
        payload = {
            "scope": args.scope,
            "raw_score_100": report.raw_score_100,
            "admission_score_100": report.admission_score_100,
            "passed": report.passed,
            "hard_gates": [gate.__dict__ for gate in report.hard_gates],
            "violations": [violation.__dict__ for violation in report.violations],
        }
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
