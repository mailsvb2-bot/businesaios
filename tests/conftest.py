from __future__ import annotations

import builtins
import os
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Tests may run on a server whose shell exports APP_ENV=prod. Keep production
# sqlite fallback fail-closed for real runtime processes, but mark pytest as an
# explicit test-local process so unit storage tests can exercise sqlite contracts.
os.environ["BUSINESAIOS_TEST_RUN"] = "1"
os.environ["BUSINESAIOS_TESTS_CONFTEST_LOADED"] = "1"
os.environ["BUSINESAIOS_ALLOW_TEST_SQLITE_FALLBACK"] = "1"

_RELEASE_INTEGRITY_TESTS = {
    "tests/test_release_clean.py",
    "tests/test_release_gate.py",
    "tests/lock/test_super_locks_no_zip_sqlite.py",
    "tests/test_canon_package_v21.py",
}


def _safe_path_part(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value.strip())
    return clean or "unknown"


def _github_actions_path_suffix() -> str:
    parts = (
        os.environ.get("GITHUB_RUN_ID", "run"),
        os.environ.get("GITHUB_RUN_ATTEMPT", "attempt"),
        os.environ.get("GITHUB_JOB", "job"),
        str(os.getpid()),
    )
    return "-".join(_safe_path_part(part) for part in parts)


def _pytest_bin_dir() -> Path:
    explicit = os.getenv("BUSINESAIOS_PYTEST_BIN_DIR")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        base = Path(explicit or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
        return base / _github_actions_path_suffix()

    if explicit:
        return Path(explicit)

    return Path(tempfile.gettempdir()) / "businesaios_pytest_bin"


class _CompatDecisionService:
    """Test-only compatibility stub for historical bare `_DecisionService()` fixtures.

    Production code must not mutate builtins or depend on this name.
    The shim lives only in pytest bootstrapping to keep tests explicit while the
    runtime stays free from hidden global wiring.
    """

    def issue(self, *args, **kwargs):
        return None


def _install_test_builtins() -> None:
    if not hasattr(builtins, "_DecisionService"):
        builtins._DecisionService = _CompatDecisionService


def _install_hermetic_python_wrappers() -> None:
    """Ensure pytest-spawned `python` children do not import host sitecustomize."""

    pytest_bin_dir = _pytest_bin_dir()
    pytest_bin_dir.mkdir(parents=True, exist_ok=True)
    site_paths = [p for p in sys.path if p and "site-packages" in p]
    pythonpath = os.pathsep.join([str(ROOT), *site_paths])
    target = str(Path(sys.executable).resolve())
    wrapper = textwrap.dedent(
        f"""\
        #!/usr/bin/env sh
        export PYTHONDONTWRITEBYTECODE=1
        if [ -n "$PYTHONPATH" ]; then
          export PYTHONPATH="{pythonpath}:$PYTHONPATH"
        else
          export PYTHONPATH="{pythonpath}"
        fi
        exec "{target}" -S "$@"
        """
    )
    for name in ("python", "python3"):
        path = pytest_bin_dir / name
        path.write_text(wrapper, encoding="utf-8")
        path.chmod(0o755)
    current_path = os.environ.get("PATH", "")
    prefix = str(pytest_bin_dir)
    if not current_path.startswith(prefix + os.pathsep):
        os.environ["PATH"] = prefix + os.pathsep + current_path


def _unlink_matching_files(base: Path, patterns: tuple[str, ...]) -> None:
    if not base.exists():
        return
    for pattern in patterns:
        for path in base.glob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink()
            except FileNotFoundError:
                pass


def _remove_runtime_artifacts() -> None:
    transient_dirs = (
        ROOT / ".runtime",
        ROOT / ".pytest_cache",
        ROOT / "tests" / "__pycache__",
        ROOT / "runtime" / "data" / "demo" / ".runtime",
    )
    for transient in transient_dirs:
        if transient.is_dir():
            shutil.rmtree(transient, ignore_errors=True)

    _unlink_matching_files(ROOT / "runtime" / "data" / "demo", ("*.db", "*.db-shm", "*.db-wal"))
    _unlink_matching_files(ROOT / "runtime" / "data" / "security", ("*.jsonl",))
    _unlink_matching_files(ROOT / "security", ("*.jsonl",))
    _unlink_matching_files(ROOT, ("wave*_*.txt",))

    if os.environ.get("BUSINESAIOS_DEEP_TEST_CLEANUP", "").strip() == "1":
        for path in ROOT.rglob("__pycache__"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
        for path in ROOT.rglob("*.pyc"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def pytest_sessionstart(session) -> None:  # type: ignore[no-untyped-def]
    _install_test_builtins()
    _install_hermetic_python_wrappers()
    _remove_runtime_artifacts()


def pytest_collection_finish(session) -> None:  # type: ignore[no-untyped-def]
    _remove_runtime_artifacts()


def pytest_sessionfinish(session, exitstatus) -> None:  # type: ignore[no-untyped-def]
    if os.environ.get("BUSINESAIOS_SESSION_FINISH_CLEANUP", "").strip() == "1":
        _remove_runtime_artifacts()


def _item_requests_runtime_artifact_cleanup(item) -> bool:  # type: ignore[no-untyped-def]
    """Return True only for tests that explicitly request artifact cleanup."""

    if os.environ.get("BUSINESAIOS_PER_TEST_CLEANUP", "").strip() == "1":
        return True
    path = Path(str(item.fspath)).resolve()
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()
    return rel in _RELEASE_INTEGRITY_TESTS or item.get_closest_marker("runtime_artifacts") is not None


def pytest_runtest_setup(item) -> None:  # type: ignore[no-untyped-def]
    if _item_requests_runtime_artifact_cleanup(item):
        _remove_runtime_artifacts()


def pytest_runtest_teardown(item, nextitem) -> None:  # type: ignore[no-untyped-def]
    if _item_requests_runtime_artifact_cleanup(item):
        _remove_runtime_artifacts()
