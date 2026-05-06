from __future__ import annotations
import atexit
from dataclasses import dataclass
from pathlib import Path
from runtime.bootstrap.bootstrap_contract import BootstrapFailureCode
from runtime.bootstrap.bootstrap_failfast import BootstrapLockError
from runtime.firewall.singleton_lock import SingletonLock
@dataclass
class BootstrapLockHandle:
    path: Path
    acquired: bool = False
class BootstrapLock:
    def __init__(self, path: str | Path) -> None:
        self._handle = BootstrapLockHandle(path=Path(path))
        self._lock = SingletonLock(path=str(self._handle.path))
        self._released = False
    @property
    def path(self) -> Path:
        return self._handle.path
    @property
    def acquired(self) -> bool:
        return self._handle.acquired
    def acquire(self) -> None:
        if self._handle.acquired:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._lock.acquire()
            self._handle.acquired = True
            atexit.register(self.release)
        except Exception as exc:
            raise BootstrapLockError(
                f"{BootstrapFailureCode.LOCK_ACQUIRE_FAILED.value}:{self.path}"
            ) from exc
    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if not self._handle.acquired:
            return
        try:
            self._lock.release()
        except Exception as exc:
            raise BootstrapLockError(
                f"{BootstrapFailureCode.LOCK_RELEASE_FAILED.value}:{self.path}"
            ) from exc
        finally:
            self._handle.acquired = False
