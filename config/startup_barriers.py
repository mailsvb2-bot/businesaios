from __future__ import annotations

CANON_COMPAT_SHIM = True

import os
import sys
import warnings

from deployment.startup_barrier_policy import StartupBarrierPolicy


def build_default_startup_barrier_policy(*, repo_root: str = ".") -> StartupBarrierPolicy:
    return StartupBarrierPolicy(
        repo_root=repo_root,
        required_directories=("boot", "runtime", "config"),
        required_files=("VERSION", "RELEASE_TAG"),
    )


def apply_startup_barriers(*, repo_root: str = ".", validate: bool = False) -> None:
    sys.dont_write_bytecode = True
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ.setdefault("PYTHONPYCACHEPREFIX", "/tmp/pycache")
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    os.environ.setdefault("DD_TRACE_ENABLED", "0")
    os.environ.setdefault("DD_TRACE_STARTUP_LOGS", "0")
    warnings.filterwarnings("ignore", message=r".*swap memory stats couldn't be determined.*", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message=r".*/proc/vmstat.*", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message=r".*swap memory stats couldn't be determined.*", category=RuntimeWarning, module=r"ddtrace\.vendor\.psutil\..*")
    if validate:
        build_default_startup_barrier_policy(repo_root=repo_root).assert_environment()
