from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

from scripts.ci.browser_evidence import BROWSER_EVIDENCE_NAME, browser_artifact_snapshot
from scripts.ci.fs import safe_write_text
from scripts.ci.paths import repo_root, reports_dir
from scripts.ci.subprocess_io import run_command


def _write(payload: dict) -> None:
    safe_write_text(reports_dir() / BROWSER_EVIDENCE_NAME, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run() -> tuple[bool, str]:
    root, frontend = repo_root(), repo_root() / "frontend"
    sha = os.environ.get("BAIOS_CI_TARGET_SHA") or None
    if shutil.which("npm") is None:
        _write({"schema": "businessaios_browser_e2e.v1", "exact_sha": sha, "status": "FAIL", "reason": "npm_missing"})
        return False, "browser-e2e: npm is unavailable"
    browser_dir = root / "artifacts" / "ci" / "browser-e2e"
    shutil.rmtree(browser_dir, ignore_errors=True)
    runtime_dir = tempfile.mkdtemp(prefix="businessaios-browser-e2e-")
    try:
        outcome = run_command(
            ["npm", "run", "test:e2e"], cwd=frontend, timeout=300,
            env={
                "CI": "1", "BAIOS_CI_TARGET_SHA": sha or "", "BAIOS_E2E_RUNTIME_DIR": runtime_dir,
                "BAIOS_E2E_PYTHON": sys.executable,
            },
        )
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
    snapshot = browser_artifact_snapshot(browser_dir)
    passed = bool(outcome.returncode == 0 and snapshot)
    _write({
        "schema": "businessaios_browser_e2e.v1", "exact_sha": sha,
        "status": "PASS" if passed and sha else "NOT_PROVEN" if passed else "FAIL", "project": "chromium",
        "stats": snapshot["stats"] if snapshot else {}, "artifacts": snapshot["artifacts"] if snapshot else {},
    })
    return passed, f"browser-e2e: {'passed' if passed else 'failed'} chromium; stats={snapshot['stats'] if snapshot else {}}"
