from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".artifacts"
REPORT = ARTIFACTS / "production_readiness_report.json"

COMMANDS = [
    {"name": "demo_boot", "cmd": [sys.executable, "main.py"], "env": {"RUN_MODE": "demo", "PYTHONPATH": "."}},
    {"name": "boot_lock_tests", "cmd": [sys.executable, "-m", "pytest", "-q", "tests/arch/test_wave2_boot_package_and_main_locks.py"], "env": {"PYTHONPATH": "."}},
    {"name": "network_boundary_test", "cmd": [sys.executable, "-m", "pytest", "-q", "tests/test_no_network_outside_effects.py"], "env": {"PYTHONPATH": "."}},
]


def _run(spec: dict[str, object]) -> dict[str, object]:
    env = os.environ.copy()
    env.update(spec.get("env", {}))  # type: ignore[arg-type]
    started = datetime.now(timezone.utc)
    proc = subprocess.run(
        spec["cmd"],  # type: ignore[arg-type]
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
    )
    finished = datetime.now(timezone.utc)
    return {
        "name": spec["name"],
        "cmd": spec["cmd"],
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "output_tail": proc.stdout[-6000:],
    }


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    results = []
    for spec in COMMANDS:
        try:
            results.append(_run(spec))
        except subprocess.TimeoutExpired as exc:
            results.append({
                "name": spec["name"],
                "cmd": spec["cmd"],
                "returncode": 124,
                "ok": False,
                "error": f"timeout after {exc.timeout}s",
                "output_tail": (exc.stdout or "")[-6000:] if isinstance(exc.stdout, str) else "",
            })
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "bounded P0 production-readiness smoke, not full production certification",
        "all_ok": all(r.get("ok") for r in results),
        "results": results,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
