from __future__ import annotations

import os
import platform
import time
from pathlib import Path
from threading import RLock

from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_bool, env_str

try:  # pragma: no cover
    import ctypes  # type: ignore
except Exception:  # pragma: no cover
    ctypes = None


class SingletonLockError(RuntimeError):
    pass


class SingletonLock:
    """Process-level singleton lock.

    Prevents multiple executors in the same deployment from executing decisions
    concurrently without an external coordinator.

    The lock file contains: `pid,created_ts`. A lock is replaced only when its
    recorded process is no longer running. A live process is never displaced
    merely because the file is old.

    Env overrides:
      - DISABLE_SINGLETON_LOCK=1  -> disable the lock entirely (debug only)

    Notes:
      - For multi-worker production deployments, you MUST rely on the durable ledger
        (Postgres) for exactly-once and optionally add advisory locks. This lock is
        an extra safety net to prevent accidental double-run in dev.
    """

    _PROCESS_LOCK = RLock()
    _PROCESS_PID = os.getpid()
    _PROCESS_HELD_PATHS: dict[str, int] = {}
    _STALE_TTL_SECONDS = 6 * 60 * 60  # compatibility constant; live owners are never stolen

    def __init__(self, path: str | None = None):
        if path is None:
            repo_root = Path(__file__).resolve().parents[2]
            from runtime.tenancy import current_tenant_id

            tenant_id = current_tenant_id()
            data_dir = env_str("DATA_DIR", "") or None
            if data_dir and str(data_dir).strip():
                base_root = Path(str(data_dir).strip()).resolve()
            else:
                base_root = (repo_root / "runtime" / "data").resolve()
            self._path = (base_root / tenant_id / "runtime_executor.lock").resolve()
        else:
            self._path = Path(path)

        self._held_count = 0
        self._held_pid: int | None = None

    def _pid_is_running(self, pid: int) -> bool:
        """Best-effort pid check without extra deps (psutil)."""
        try:
            pid = int(pid)
        except Exception:
            return False
        if pid <= 0:
            return False

        system = platform.system().lower()
        if system.startswith("win") and ctypes is not None:
            try:
                process_query_limited_information = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, 0, pid)
                if handle == 0:
                    return False
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            except Exception:
                return False

        if hasattr(os, "kill"):
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            except Exception:
                return False

        try:
            return Path(f"/proc/{pid}").exists()
        except Exception:
            return False

    def _parse_lockfile(self) -> tuple[int, int | None]:
        """Return (pid, created_ts) from the lock file. created_ts may be None."""
        try:
            raw = self._path.read_text(encoding="utf-8").strip()
            parts = raw.split(",")
            lock_pid = int(parts[0]) if parts and parts[0] else -1
            created_ts = int(parts[1]) if len(parts) > 1 and parts[1] else None
            return lock_pid, created_ts
        except Exception:
            return -1, None

    def _create_lockfile(self, *, flags: int, pid: int, now: int) -> None:
        fd: int | None = None
        created = False
        primary_error: BaseException | None = None
        try:
            fd = os.open(str(self._path), flags, 0o644)
            created = True
            payload = f"{pid},{now}".encode()
            offset = 0
            while offset < len(payload):
                written = os.write(fd, payload[offset:])
                if written <= 0:
                    raise OSError("singleton lock write made no progress")
                offset += int(written)
            os.fsync(fd)
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException as close_exc:
                    if primary_error is not None:
                        primary_error.add_note(f"singleton lock close also failed: {close_exc}")
                    else:
                        primary_error = close_exc
            if primary_error is not None:
                if created:
                    try:
                        self._path.unlink(missing_ok=True)
                    except BaseException as unlink_exc:
                        primary_error.add_note(f"singleton lock cleanup also failed: {unlink_exc}")
                if not isinstance(primary_error, SingletonLockError):
                    raise SingletonLockError(f"RuntimeExecutor lock could not be created: {self._path}") from primary_error
                raise primary_error

    @classmethod
    def _sync_process_registry(cls, pid: int) -> None:
        if cls._PROCESS_PID == int(pid):
            return
        cls._PROCESS_HELD_PATHS.clear()
        cls._PROCESS_PID = int(pid)

    def _mark_process_held(self, path_key: str, *, pid: int) -> None:
        self._PROCESS_HELD_PATHS[path_key] = self._PROCESS_HELD_PATHS.get(path_key, 0) + 1
        if self._held_pid != int(pid):
            self._held_count = 0
            self._held_pid = int(pid)
        self._held_count += 1

    def acquire(self) -> None:
        if env_bool("DISABLE_SINGLETON_LOCK", False):
            return

        path_key = str(self._path.resolve())
        pid = os.getpid()
        with self._PROCESS_LOCK:
            self._sync_process_registry(pid)
            if self._PROCESS_HELD_PATHS.get(path_key, 0) > 0:
                self._mark_process_held(path_key, pid=pid)
                return

            self._path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            now = int(time.time())

            try:
                self._create_lockfile(flags=flags, pid=pid, now=now)
                self._mark_process_held(path_key, pid=pid)
                return
            except SingletonLockError as exc:
                if not isinstance(exc.__cause__, FileExistsError):
                    raise

            lock_pid, _created_ts = self._parse_lockfile()
            if lock_pid == pid:
                self._mark_process_held(path_key, pid=pid)
                return

            if self._pid_is_running(lock_pid):
                raise SingletonLockError(f"RuntimeExecutor already running (pid={lock_pid}, lock: {self._path})")

            try:
                self._path.unlink(missing_ok=True)
            except Exception as exc:
                raise SingletonLockError(
                    f"RuntimeExecutor lock exists but cannot be cleared: {self._path}"
                ) from exc

            try:
                self._create_lockfile(flags=flags, pid=pid, now=now)
            except SingletonLockError as exc:
                if isinstance(exc.__cause__, FileExistsError):
                    raise SingletonLockError(f"RuntimeExecutor already running (lock: {self._path})") from exc
                raise
            self._mark_process_held(path_key, pid=pid)

    def release(self) -> None:
        path_key = str(self._path.resolve())
        pid = os.getpid()
        with self._PROCESS_LOCK:
            self._sync_process_registry(pid)
            if self._held_pid != pid or self._held_count <= 0:
                self._held_count = 0
                self._held_pid = None
                return
            self._held_count -= 1

            held_count = self._PROCESS_HELD_PATHS.get(path_key, 0)
            if held_count > 1:
                self._PROCESS_HELD_PATHS[path_key] = held_count - 1
                return
            self._PROCESS_HELD_PATHS.pop(path_key, None)

            self._held_pid = None
            lock_pid, _ = self._parse_lockfile()
            if lock_pid != pid:
                return
            try:
                self._path.unlink(missing_ok=True)
            except Exception:
                swallow(__name__, "runtime/firewall/singleton_lock.py")
