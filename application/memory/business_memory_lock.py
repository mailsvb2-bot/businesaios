from __future__ import annotations
import os, time
from dataclasses import dataclass
from pathlib import Path
CANON_BUSINESS_MEMORY_LOCK = True
@dataclass(frozen=True)
class FileBusinessMemoryLock:
    target_path: Path
    timeout_seconds: float = 5.0
    retry_delay_seconds: float = 0.05
    def __enter__(self) -> "FileBusinessMemoryLock":
        lock_path=self._lock_path(); deadline=time.monotonic()+float(self.timeout_seconds)
        while True:
            try:
                fd=os.open(str(lock_path), os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.close(fd); return self
            except FileExistsError:
                if time.monotonic() >= deadline: raise TimeoutError(f"Timed out acquiring business memory lock: {lock_path}")
                time.sleep(float(self.retry_delay_seconds))
    def __exit__(self, exc_type, exc, tb) -> None:
        try: self._lock_path().unlink()
        except FileNotFoundError: return
    def _lock_path(self) -> Path:
        return self.target_path.with_suffix(self.target_path.suffix + ".lock")
__all__=["CANON_BUSINESS_MEMORY_LOCK", "FileBusinessMemoryLock"]
