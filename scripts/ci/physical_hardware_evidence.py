from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path

from scripts.ci.fs import safe_write_text

PHYSICAL_HARDWARE_SCHEMA = "businessaios_physical_hardware_evidence.v1"


def _exact_sha(value: str) -> bool:
    return len(value) == 40 and value == value.lower() and all(ch in "0123456789abcdef" for ch in value)


def build_evidence(*, acceptance_report: Path, exact_sha: str, runner: str) -> dict[str, object]:
    if platform.system().lower() != "windows":
        raise RuntimeError("physical hardware evidence must be produced on Windows")
    if not _exact_sha(exact_sha):
        raise RuntimeError("exact_sha must be a lowercase 40-character SHA")
    payload = json.loads(acceptance_report.read_text(encoding="utf-8"))
    steps = payload.get("steps") if isinstance(payload, dict) else None
    user_step = next((item for item in steps or [] if isinstance(item, dict) and item.get("name") == "user-scenario-gate"), None)
    passed = bool(payload.get("gate") == "acceptance" and payload.get("success") is True and user_step and user_step.get("status") == "passed")
    return {
        "schema": PHYSICAL_HARDWARE_SCHEMA,
        "status": "PASS" if passed else "FAIL",
        "exact_sha": exact_sha,
        "platform": "windows",
        "runner": runner,
        "acceptance_gate": "PASS" if passed else "FAIL",
        "source_artifact": acceptance_report.name,
        "claims_production_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acceptance-report", type=Path, required=True)
    parser.add_argument("--exact-sha", required=True)
    parser.add_argument("--runner", default=os.getenv("RUNNER_NAME", "physical-windows"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = build_evidence(acceptance_report=args.acceptance_report, exact_sha=args.exact_sha, runner=args.runner)
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"[physical-hardware-evidence] blocked: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    safe_write_text(args.output, json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[physical-hardware-evidence] status={evidence['status']} exact_sha={evidence['exact_sha']}")
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
