from __future__ import annotations

import argparse
import os
import sys

from scripts.ci.contracts import ExecutionRequest
from scripts.ci.execution import execute
from scripts.ci.plan_registry import allowed_gates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", choices=allowed_gates(), required=True)
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--no-junit", action="store_true")
    parser.add_argument("--no-coverage", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = execute(
        ExecutionRequest(
            gate=args.gate,
            emit_report=not args.no_report,
            emit_junit=not args.no_junit,
            emit_coverage=not args.no_coverage,
        )
    )

    print(f"[ci] goal: {report.goal}")
    print(f"[ci] gate: {report.gate}")
    print(f"[ci] success: {report.success}")
    for step in report.steps:
        print(
            f"[ci] step={step.name} status={step.status} "
            f"duration_ms={step.duration_ms} message={step.message}"
        )
    return 0 if report.success else 1


if __name__ == "__main__":
    # In hosted CI/sandbox environments, imported telemetry/platform packages can
    # register shutdown hooks that keep the interpreter alive after all project
    # checks have completed. The CLI has already printed and flushed its bounded
    # report by this point, so exit hard to preserve deterministic CI behavior.
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
