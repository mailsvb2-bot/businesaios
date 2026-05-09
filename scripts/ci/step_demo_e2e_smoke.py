from __future__ import annotations

from scripts.ci.subprocess_io import run_command


def run() -> tuple[bool, str]:
    outcome = run_command(
        ["python", "main.py"],
        env={
            "RUN_MODE": "demo",
            "DEMO_E2E_SMOKE": "1",
            "APP_ENV": "ci",
            "ENV": "ci",
            "TENANT_ID": "ci-demo-tenant",
            "SYSTEM_TZ": "Europe/Amsterdam",
            "CI_STEP_TIMEOUT_SECONDS": "180",
        },
        timeout=180,
    )
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, "demo e2e smoke timed out"
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "demo e2e smoke failed"
    return True, "demo e2e smoke passed"


__all__ = ["run"]
