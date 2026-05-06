#!/usr/bin/env python3
"""P0 import-smoke gate for canonical BusinesAIOS entrypoints."""
from __future__ import annotations
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = int(os.environ.get("IMPORT_SMOKE_TIMEOUT", "12"))
TARGETS = (
    "main",
    "core.ai.decision_core",
    "runtime.decision_gateway",
    "runtime.execution.execution_path_lock",
    "application.headless.closed_loop",
    "entrypoints.api.fastapi_app_factory",
    "app.web.app",
)

@dataclass(frozen=True)
class ImportResult:
    target: str
    ok: bool
    detail: str

def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    env.setdefault("DD_TRACE_ENABLED", "0")
    env.setdefault("DD_TRACE_STARTUP_LOGS", "0")
    env["PYTHONPATH"] = str(REPO_ROOT)
    return env

def check_import(target: str) -> ImportResult:
    code = "import importlib; importlib.import_module(%r); print('OK %s')" % (target, target)
    try:
        proc = subprocess.run(
            [sys.executable, "-S", "-c", code],
            cwd=str(REPO_ROOT),
            env=_env(),
            text=True,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ImportResult(target, False, f"TIMEOUT after {TIMEOUT_SECONDS}s")
    if proc.returncode == 0:
        return ImportResult(target, True, proc.stdout.strip())
    detail = (proc.stderr or proc.stdout or "import failed").strip()
    return ImportResult(target, False, detail[-4000:])

def main() -> int:
    results = [check_import(target) for target in TARGETS]
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.target}")
        if not result.ok:
            print(result.detail)
    return 0 if all(result.ok for result in results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
