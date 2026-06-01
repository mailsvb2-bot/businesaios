"""Hermetic test runner.

Use this instead of `pytest` if your environment preloads ddtrace or other
plugins (which can produce warnings or break collection).

Runs:
- compileall
- pytest

with environment barriers:
- disables external pytest plugin autoload
- disables ddtrace auto-instrumentation
- disables bytecode writing
- silences known noisy RuntimeWarnings
"""

from __future__ import annotations

import compileall
import os
import sys
import warnings

from core.observability.silent import swallow
from runtime.platform.config.env_flags import env_str


def _clean_build_artifacts(root: str = ".") -> None:
    """Remove local build/runtime artifacts so canonical invariants can pass.

    This is intentionally aggressive for hermetic test runs.
    """
    import shutil
    from pathlib import Path

    r = Path(root).resolve()

    # Python caches
    for p in r.rglob("__pycache__"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    for p in r.rglob("*.pyc"):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            swallow(__name__, 'scripts/run_tests_clean.py')

    # Tool caches
    for d in [".pytest_cache", ".mypy_cache", ".ruff_cache"]:
        for p in r.rglob(d):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)

    # Runtime artifacts (sqlite + locks) — never committed
    for ext in [".db", ".sqlite", ".sqlite3"]:
        for f in r.rglob(f"*{ext}"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                swallow(__name__, 'scripts/run_tests_clean.py')

    # Known lock files
    for f in r.rglob("*.lock"):
        try:
            f.unlink(missing_ok=True)
        except Exception:
            swallow(__name__, 'scripts/run_tests_clean.py')





def main() -> int:
    # Re-exec once with PYTHONWARNINGS set before interpreter startup.
    # This is the only reliable way to suppress warnings emitted from globally
    # preloaded sitecustomize (e.g., ddtrace in some environments).
    if env_str("BUSINESAIOS_HERMETIC_REEXEC", "") != "1":
        os.environ["BUSINESAIOS_HERMETIC_REEXEC"] = "1"
        os.environ.setdefault(
            "PYTHONWARNINGS",
            "ignore:.*swap memory stats couldn't be determined.*:RuntimeWarning,ignore:.*\\/proc\\/vmstat.*:RuntimeWarning",
        )
        os.execv(sys.executable, [sys.executable, __file__])

    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    # Also set runtime flag (compileall checks sys.dont_write_bytecode).
    sys.dont_write_bytecode = True
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    os.environ.setdefault("DD_TRACE_ENABLED", "false")
    os.environ.setdefault("DD_TRACE_STARTUP_LOGS", "0")

    # Silence noisy external-environment warnings.
    warnings.filterwarnings(
        "ignore",
        message=r".*swap memory stats couldn't be determined.*",
        category=RuntimeWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r".*\/proc\/vmstat.*",
        category=RuntimeWarning,
    )

    ok = compileall.compile_dir(".", quiet=1)
    # compileall may produce __pycache__ artifacts; remove them before pytest invariants.
    _clean_build_artifacts(".")
    if not ok:
        return 2

    import pytest  # noqa: WPS433

    return int(pytest.main(["-q"]))


if __name__ == "__main__":
    raise SystemExit(main())
