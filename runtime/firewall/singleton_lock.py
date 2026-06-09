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
    _PROCESS_LOCK = RLock()
    _PROCESS_HELD_PATHS: dict[str, int] = {}

    """Process-level singleton lock.

    Prevents multiple executors in the same deployment from executing decisions
    concurrently without an external coordinator.

    The lock file contains: `pid,created_ts`.
    If the lock exists but is stale (pid not running OR very old), it is replaced.

    Env overrides:
      - DISABLE_SINGLETON_LOCK=1  -> disable the lock entirely (debug only)

    Notes:
      - For multi-worker production deployments, you MUST rely on the durable ledger
        (Postgres) for exactly-once and optionally add advisory locks. This lock is
        an extra safety net to prevent accidental double-run in dev.
    """

    _STALE_TTL_SECONDS = 6 * 60 * 60  # 6 hours

    def __init__(self, path: str | None = None):
        # Canonical tenant-scoped lock path (unless explicitly provided).
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

        self._fd: int | None = None

    def _pid_is_running(self, pid: int) -> bool:
        """Best-effort pid check without extra deps (psutil).

        - On Windows: OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)
        - Elsewhere: os.kill(pid, 0)
        """

        try:
            pid = int(pid)
        except Exception:
            return False
        if pid <= 0:
            return False

        system = platform.system().lower()
        if system.startswith("win") and ctypes is not None:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if handle == 0:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True

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

        # Last resort: if /proc exists, check directory presence.
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

    def acquire(self) -> None:
        if env_bool("DISABLE_SINGLETON_LOCK", False):
            return

        path_key = str(self._path.resolve())
        with self._PROCESS_LOCK:
            held_count = self._PROCESS_HELD_PATHS.get(path_key, 0)
            if held_count > 0:
                self._PROCESS_HELD_PATHS[path_key] = held_count + 1
                return

            self._path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            pid = os.getpid()
            now = int(time.time())

            try:
                self._fd = os.open(str(self._path), flags, 0o644)
                os.write(self._fd, f"{pid},{now}".encode())
                self._PROCESS_HELD_PATHS[path_key] = 1
                return
            except FileExistsError:
                lock_pid, created_ts = self._parse_lockfile()

                if lock_pid == pid:
                    self._PROCESS_HELD_PATHS[path_key] = 1
                    return

                stale = False
                if created_ts is not None:
                    try:
                        if (int(time.time()) - int(created_ts)) > self._STALE_TTL_SECONDS:
                            stale = True
                    except Exception:
                        stale = True

                if stale or (not self._pid_is_running(lock_pid)):
                    try:
                        self._path.unlink(missing_ok=True)
                    except Exception as e:
                        raise SingletonLockError(
                            f"RuntimeExecutor lock exists but cannot be cleared: {self._path}"
                        ) from e

                    try:
                        self._fd = os.open(str(self._path), flags, 0o644)
                        os.write(self._fd, f"{pid},{now}".encode())
                        self._PROCESS_HELD_PATHS[path_key] = 1
                        return
                    except FileExistsError as e:
                        raise SingletonLockError(f"RuntimeExecutor already running (lock: {self._path})") from e

                raise SingletonLockError(f"RuntimeExecutor already running (pid={lock_pid}, lock: {self._path})")

    def release(self) -> None:
        path_key = str(self._path.resolve())
        with self._PROCESS_LOCK:
            held_count = self._PROCESS_HELD_PATHS.get(path_key, 0)
            if held_count > 1:
                self._PROCESS_HELD_PATHS[path_key] = held_count - 1
                return
            self._PROCESS_HELD_PATHS.pop(path_key, None)

            if self._fd is not None:
                try:
                    os.close(self._fd)
                finally:
                    self._fd = None
                try:
                    self._path.unlink(missing_ok=True)
                except Exception:
                    swallow(__name__, 'runtime/firewall/singleton_lock.py')
                return

            lock_pid, _ = self._parse_lockfile()
            if lock_pid == os.getpid():
                try:
                    self._path.unlink(missing_ok=True)
                except Exception:
                    swallow(__name__, 'runtime/firewall/singleton_lock.py')
