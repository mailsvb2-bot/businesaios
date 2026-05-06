from __future__ import annotations

import builtins
import os
import shutil
import sys
import textwrap
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent
PYTEST_BIN_DIR = Path(os.getenv("BUSINESAIOS_PYTEST_BIN_DIR", "/tmp/businesaios_pytest_bin"))

class _CompatDecisionService:
    """Test-only compatibility stub for historical bare `_DecisionService()` fixtures.

    Production code must not mutate builtins or depend on this name.
    The shim lives only in pytest bootstrapping to keep tests explicit while the
    runtime stays free from hidden global wiring.
    """

    def issue(self, *args, **kwargs):
        return None

def _install_test_builtins() -> None:
    if not hasattr(builtins, '_DecisionService'):
        builtins._DecisionService = _CompatDecisionService

def _install_hermetic_python_wrappers() -> None:
    """Ensure pytest-spawned `python` children do not import host sitecustomize.

    Some tests intentionally spawn Python subprocesses. In this execution
    environment, the host-level `/opt/python-hooks/sitecustomize.py` can add
    unrelated artifact-tool side effects to those children. The project test
    harness owns hermeticity, so child `python`/`python3` launched through PATH
    are routed through `sys.executable -S` with an explicit PYTHONPATH. The
    current pytest interpreter is not replaced.
    """

    PYTEST_BIN_DIR.mkdir(parents=True, exist_ok=True)
    site_paths = [p for p in sys.path if p and 'site-packages' in p]
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
    for name in ('python', 'python3'):
        path = PYTEST_BIN_DIR / name
        path.write_text(wrapper, encoding='utf-8')
        path.chmod(0o755)
    current_path = os.environ.get('PATH', '')
    prefix = str(PYTEST_BIN_DIR)
    if not current_path.startswith(prefix + os.pathsep):
        os.environ['PATH'] = prefix + os.pathsep + current_path

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
        ROOT / '.runtime',
        ROOT / '.pytest_cache',
        ROOT / 'runtime' / 'data' / 'demo' / '.runtime',
    )
    for transient in transient_dirs:
        if transient.is_dir():
            shutil.rmtree(transient, ignore_errors=True)

    _unlink_matching_files(ROOT / 'runtime' / 'data' / 'demo', ('*.db', '*.db-shm', '*.db-wal'))
    _unlink_matching_files(ROOT, ('wave*_*.txt',))

    if os.environ.get('BUSINESAIOS_DEEP_TEST_CLEANUP', '').strip() == '1':
        for path in ROOT.rglob('__pycache__'):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
        for path in ROOT.rglob('*.pyc'):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

def pytest_sessionstart(session) -> None:  # type: ignore[no-untyped-def]
    _install_test_builtins()
    _install_hermetic_python_wrappers()
    _remove_runtime_artifacts()

def pytest_sessionfinish(session, exitstatus) -> None:  # type: ignore[no-untyped-def]
    if os.environ.get('BUSINESAIOS_SESSION_FINISH_CLEANUP', '').strip() == '1':
        _remove_runtime_artifacts()

def _item_requests_runtime_artifact_cleanup(item) -> bool:  # type: ignore[no-untyped-def]
    """Return True only for tests that explicitly request artifact cleanup."""

    if os.environ.get("BUSINESAIOS_PER_TEST_CLEANUP", "").strip() == "1":
        return True
    return item.get_closest_marker("runtime_artifacts") is not None

def pytest_runtest_setup(item) -> None:  # type: ignore[no-untyped-def]
    if _item_requests_runtime_artifact_cleanup(item):
        _remove_runtime_artifacts()

def pytest_runtest_teardown(item, nextitem) -> None:  # type: ignore[no-untyped-def]
    if _item_requests_runtime_artifact_cleanup(item):
        _remove_runtime_artifacts()
