from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from scripts.ci.fs import safe_write_text
from scripts.ci.paths import repo_root, reports_dir
from scripts.ci.subprocess_io import run_command

_EVIDENCE = "browser-e2e-evidence.json"


def _write(payload: dict) -> None:
    safe_write_text(reports_dir() / _EVIDENCE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _playwright_stats(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    stats = payload.get("stats") if isinstance(payload, dict) else None
    return stats if isinstance(stats, dict) else None


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
    stats = _playwright_stats(browser_dir / "playwright.json")
    diagnostics = all(path.exists() for path in (browser_dir / "junit.xml", browser_dir / "html" / "index.html"))
    passed = bool(
        outcome.returncode == 0 and stats and diagnostics and int(stats.get("expected", 0)) > 0
        and int(stats.get("unexpected", 0)) == 0 and int(stats.get("skipped", 0)) == 0
    )
    _write({
        "schema": "businessaios_browser_e2e.v1", "exact_sha": sha,
        "status": "PASS" if passed and sha else "NOT_PROVEN" if passed else "FAIL",
        "project": "chromium", "stats": stats or {},
        "artifacts": {"junit": "browser-e2e/junit.xml", "json": "browser-e2e/playwright.json", "html": "browser-e2e/html/index.html"},
    })
    return passed, f"browser-e2e: {'passed' if passed else 'failed'} chromium; stats={stats or {}}"
