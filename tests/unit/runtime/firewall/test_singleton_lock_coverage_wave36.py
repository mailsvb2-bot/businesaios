from __future__ import annotations

import os
import time
from multiprocessing import get_all_start_methods, get_context
from pathlib import Path
from types import SimpleNamespace

import pytest

import runtime.firewall.singleton_lock as module
from runtime.firewall.singleton_lock import SingletonLock, SingletonLockError


def _hold_lock(path: str, ready, release) -> None:
    lock = SingletonLock(path)
    lock.acquire()
    ready.set()
    release.wait(15)
    lock.release()


def _fork_contender(path: str, results) -> None:
    lock = SingletonLock(path)
    try:
        lock.acquire()
    except SingletonLockError:
        results.put("blocked")
    else:
        results.put("acquired")
        lock.release()


def _fork_release_inherited(lock: SingletonLock, path: str, results) -> None:
    lock.release()
    results.put(Path(path).exists())


@pytest.fixture(autouse=True)
def clear_process_registry() -> None:
    SingletonLock._PROCESS_PID = os.getpid()
    SingletonLock._PROCESS_HELD_PATHS.clear()
    yield
    SingletonLock._PROCESS_PID = os.getpid()
    SingletonLock._PROCESS_HELD_PATHS.clear()


def test_default_path_explicit_path_and_disabled_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("runtime.tenancy.current_tenant_id", lambda: "tenant-a")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    default = SingletonLock()
    assert default._path == (tmp_path / "data" / "tenant-a" / "runtime_executor.lock").resolve()

    monkeypatch.setenv("DATA_DIR", "")
    fallback = SingletonLock()
    assert fallback._path.name == "runtime_executor.lock"
    assert fallback._path.parent.name == "tenant-a"

    explicit = SingletonLock(str(tmp_path / "explicit.lock"))
    monkeypatch.setenv("DISABLE_SINGLETON_LOCK", "1")
    explicit.acquire()
    explicit.release()
    assert explicit._held_count == 0
    assert not explicit._path.exists()


def test_pid_checks_cover_posix_windows_and_proc_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = SingletonLock(str(tmp_path / "lock"))
    assert lock._pid_is_running("bad") is False
    assert lock._pid_is_running(0) is False

    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module.os, "kill", lambda pid, signal: None)
    assert lock._pid_is_running(10) is True

    def lookup(pid, signal):
        raise ProcessLookupError

    monkeypatch.setattr(module.os, "kill", lookup)
    assert lock._pid_is_running(10) is False

    def denied(pid, signal):
        raise PermissionError

    monkeypatch.setattr(module.os, "kill", denied)
    assert lock._pid_is_running(10) is True

    def broken(pid, signal):
        raise RuntimeError("broken")

    monkeypatch.setattr(module.os, "kill", broken)
    assert lock._pid_is_running(10) is False

    class Kernel:
        def __init__(self, handle: int) -> None:
            self.handle = handle
            self.closed: list[int] = []

        def OpenProcess(self, access, inherit, pid):
            return self.handle

        def CloseHandle(self, handle):
            self.closed.append(handle)

    kernel = Kernel(42)
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(module, "ctypes", SimpleNamespace(windll=SimpleNamespace(kernel32=kernel)))
    assert lock._pid_is_running(10) is True
    assert kernel.closed == [42]

    kernel.handle = 0
    assert lock._pid_is_running(10) is False
    monkeypatch.setattr(module, "ctypes", SimpleNamespace())
    assert lock._pid_is_running(10) is False

    monkeypatch.setattr(module.platform, "system", lambda: "Other")
    monkeypatch.delattr(module.os, "kill", raising=False)
    original_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: str(self) == "/proc/10")
    assert lock._pid_is_running(10) is True
    monkeypatch.setattr(Path, "exists", lambda self: (_ for _ in ()).throw(RuntimeError("fs")))
    assert lock._pid_is_running(10) is False
    monkeypatch.setattr(Path, "exists", original_exists)


def test_parse_create_partial_write_and_failure_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "runtime.lock"
    lock = SingletonLock(str(path))
    assert lock._parse_lockfile() == (-1, None)
    path.write_text("123,456", encoding="utf-8")
    assert lock._parse_lockfile() == (123, 456)
    path.write_text("123", encoding="utf-8")
    assert lock._parse_lockfile() == (123, None)
    path.write_text("broken", encoding="utf-8")
    assert lock._parse_lockfile() == (-1, None)
    path.unlink()

    original_write = os.write

    def partial(fd: int, payload: bytes) -> int:
        return original_write(fd, payload[:2])

    monkeypatch.setattr(module.os, "write", partial)
    lock._create_lockfile(flags=os.O_CREAT | os.O_EXCL | os.O_WRONLY, pid=12, now=34)
    assert path.read_text(encoding="utf-8") == "12,34"
    path.unlink()

    monkeypatch.setattr(module.os, "write", lambda fd, payload: 0)
    with pytest.raises(SingletonLockError, match="could not be created"):
        lock._create_lockfile(flags=os.O_CREAT | os.O_EXCL | os.O_WRONLY, pid=12, now=34)
    assert not path.exists()

    path.write_text("foreign", encoding="utf-8")
    with pytest.raises(SingletonLockError) as raised:
        lock._create_lockfile(flags=os.O_CREAT | os.O_EXCL | os.O_WRONLY, pid=12, now=34)
    assert isinstance(raised.value.__cause__, FileExistsError)
    assert path.read_text(encoding="utf-8") == "foreign"


def test_create_cleanup_notes_close_and_unlink_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "runtime.lock"
    lock = SingletonLock(str(path))
    original_close = os.close
    opened: list[int] = []

    def close_fails(fd: int) -> None:
        opened.append(fd)
        raise OSError("close failed")

    monkeypatch.setattr(module.os, "close", close_fails)
    with pytest.raises(SingletonLockError, match="could not be created") as raised:
        lock._create_lockfile(flags=os.O_CREAT | os.O_EXCL | os.O_WRONLY, pid=1, now=2)
    assert isinstance(raised.value.__cause__, OSError)
    assert not path.exists()
    for fd in opened:
        original_close(fd)

    monkeypatch.setattr(module.os, "close", original_close)
    monkeypatch.setattr(module.os, "write", lambda fd, payload: (_ for _ in ()).throw(OSError("write failed")))
    original_unlink = Path.unlink
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(OSError("unlink failed")))
    with pytest.raises(SingletonLockError, match="could not be created") as raised:
        lock._create_lockfile(flags=os.O_CREAT | os.O_EXCL | os.O_WRONLY, pid=1, now=2)
    assert any("cleanup also failed" in note for note in raised.value.__cause__.__notes__)
    monkeypatch.setattr(Path, "unlink", original_unlink)
    if path.exists():
        path.unlink()


def test_reentrant_instances_release_order_and_unacquired_release(tmp_path: Path) -> None:
    path = tmp_path / "runtime.lock"
    first = SingletonLock(str(path))
    second = SingletonLock(str(path))
    stranger = SingletonLock(str(path))

    first.acquire()
    second.acquire()
    first.acquire()
    assert first._held_count == 2
    assert second._held_count == 1
    assert SingletonLock._PROCESS_HELD_PATHS[str(path.resolve())] == 3

    stranger.release()
    assert path.exists()
    first.release()
    assert path.exists()
    first.release()
    assert path.exists()
    second.release()
    assert not path.exists()
    second.release()

    first.acquire()
    second.acquire()
    second.release()
    assert path.exists()
    first.release()
    assert not path.exists()


def test_live_old_lock_is_never_stolen_and_dead_lock_is_replaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "runtime.lock"
    lock = SingletonLock(str(path))
    path.write_text("999,1", encoding="utf-8")
    monkeypatch.setattr(module.os, "getpid", lambda: 100)
    monkeypatch.setattr(lock, "_pid_is_running", lambda pid: True)
    with pytest.raises(SingletonLockError, match="already running"):
        lock.acquire()
    assert path.read_text(encoding="utf-8") == "999,1"

    monkeypatch.setattr(lock, "_pid_is_running", lambda pid: False)
    lock.acquire()
    assert path.read_text(encoding="utf-8").startswith("100,")
    lock.release()
    assert not path.exists()

    path.write_text("broken", encoding="utf-8")
    lock.acquire()
    lock.release()
    assert not path.exists()


def _file_exists_error(path: Path) -> SingletonLockError:
    try:
        raise FileExistsError(str(path))
    except FileExistsError as exc:
        raise SingletonLockError("exists") from exc


def test_stale_clear_fail_race_and_non_file_exists_create_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "runtime.lock"
    lock = SingletonLock(str(path))
    path.write_text("999,1", encoding="utf-8")
    monkeypatch.setattr(lock, "_pid_is_running", lambda pid: False)

    original_unlink = Path.unlink
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(OSError("denied")))
    with pytest.raises(SingletonLockError, match="cannot be cleared"):
        lock.acquire()
    monkeypatch.setattr(Path, "unlink", original_unlink)

    calls = 0

    def race(**kwargs):
        nonlocal calls
        calls += 1
        _file_exists_error(path)

    monkeypatch.setattr(lock, "_create_lockfile", race)
    with pytest.raises(SingletonLockError, match="already running"):
        lock.acquire()
    assert calls == 2

    def broken(**kwargs):
        raise SingletonLockError("broken") from RuntimeError("write")

    if path.exists():
        path.unlink()
    monkeypatch.setattr(lock, "_create_lockfile", broken)
    with pytest.raises(SingletonLockError, match="broken"):
        lock.acquire()


def test_release_does_not_delete_foreign_replacement_and_swallows_unlink_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "runtime.lock"
    lock = SingletonLock(str(path))
    lock.acquire()
    path.write_text("999,1", encoding="utf-8")
    lock.release()
    assert path.exists()

    path.unlink()
    lock.acquire()
    swallowed: list[tuple[str, str]] = []
    monkeypatch.setattr(module, "swallow", lambda name, where: swallowed.append((name, where)))
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(OSError("denied")))
    lock.release()
    assert swallowed and swallowed[0][1] == "runtime/firewall/singleton_lock.py"



@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded.*:DeprecationWarning")
def test_forked_process_cannot_inherit_registry_or_release_parent_lock(tmp_path: Path) -> None:
    if "fork" not in get_all_start_methods():
        pytest.skip("fork start method unavailable")
    context = get_context("fork")
    path = str(tmp_path / "runtime.lock")
    parent_lock = SingletonLock(path)
    parent_lock.acquire()

    results = context.Queue()
    inherited_release = context.Process(
        target=_fork_release_inherited,
        args=(parent_lock, path, results),
    )
    inherited_release.start()
    inherited_release.join(timeout=10)
    assert inherited_release.exitcode == 0
    assert results.get(timeout=5) is True
    assert Path(path).exists()

    contender = context.Process(target=_fork_contender, args=(path, results))
    contender.start()
    contender.join(timeout=10)
    assert contender.exitcode == 0
    assert results.get(timeout=5) == "blocked"
    assert Path(path).exists()

    parent_lock.release()
    assert not Path(path).exists()


def test_cross_process_contention_and_recovery_after_release(tmp_path: Path) -> None:
    context = get_context("spawn")
    ready = context.Event()
    release = context.Event()
    path = str(tmp_path / "runtime.lock")
    process = context.Process(target=_hold_lock, args=(path, ready, release))
    process.start()
    assert ready.wait(10)

    contender = SingletonLock(path)
    with pytest.raises(SingletonLockError, match="already running"):
        contender.acquire()

    release.set()
    process.join(timeout=20)
    assert process.exitcode == 0
    contender.acquire()
    contender.release()
    assert not Path(path).exists()


def test_remaining_creation_and_adoption_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "runtime.lock"
    lock = SingletonLock(str(path))
    original_close = os.close
    opened: list[int] = []

    monkeypatch.setattr(module.os, "write", lambda fd, payload: (_ for _ in ()).throw(OSError("write failed")))

    def close_fails(fd: int) -> None:
        opened.append(fd)
        raise OSError("close failed")

    monkeypatch.setattr(module.os, "close", close_fails)
    with pytest.raises(SingletonLockError, match="could not be created") as raised:
        lock._create_lockfile(flags=os.O_CREAT | os.O_EXCL | os.O_WRONLY, pid=1, now=2)
    assert any("close also failed" in note for note in raised.value.__cause__.__notes__)
    for fd in opened:
        original_close(fd)
    if path.exists():
        path.unlink()

    monkeypatch.setattr(module.os, "close", original_close)
    monkeypatch.setattr(module.os, "write", lambda fd, payload: (_ for _ in ()).throw(SingletonLockError("inner")))
    with pytest.raises(SingletonLockError, match="inner"):
        lock._create_lockfile(flags=os.O_CREAT | os.O_EXCL | os.O_WRONLY, pid=1, now=2)
    assert not path.exists()

    monkeypatch.setattr(module.os, "write", os.write)
    path.write_text(f"{os.getpid()},1", encoding="utf-8")
    lock.acquire()
    assert lock._held_count == 1
    lock.release()
    assert not path.exists()

    path.write_text("999,1", encoding="utf-8")
    monkeypatch.setattr(lock, "_pid_is_running", lambda pid: False)
    calls = 0

    def second_fails(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            _file_exists_error(path)
        raise SingletonLockError("replacement failed") from RuntimeError("write")

    monkeypatch.setattr(lock, "_create_lockfile", second_fails)
    with pytest.raises(SingletonLockError, match="replacement failed"):
        lock.acquire()
    assert calls == 2
