"""Canonical durable mutation boundary for tenant/product offer catalogs."""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ModuleNotFoundError:  # pragma: no cover - non-POSIX fallback
    _fcntl = None

from config.yaml_loader_shared import invalidate_yaml_cache
from runtime.platform.config.env_flags import env_float, env_path, env_str

CANON_OFFER_CATALOG_MUTATION_OWNER = True

_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, Any] = {}


@dataclass
class CatalogMutationLock:
    lock_path: Path
    process_lock: Any
    handle: Any
    released: bool = False

    def release(self) -> None:
        if self.released:
            return
        try:
            if _fcntl is not None and self.handle is not None:
                _fcntl.flock(self.handle.fileno(), _fcntl.LOCK_UN)
        finally:
            try:
                if self.handle is not None:
                    self.handle.close()
            finally:
                self.process_lock.release()
                self.released = True


def acquire_catalog_lock(catalog_path: Path, *, timeout_s: float | None = None) -> CatalogMutationLock:
    lock_path = catalog_path.with_suffix(catalog_path.suffix + ".mutation.lock")
    key = str(lock_path)
    with _PROCESS_LOCKS_GUARD:
        process_lock = _PROCESS_LOCKS.setdefault(key, threading.Lock())
    timeout = float(timeout_s) if timeout_s is not None else env_float(
        "OFFER_CATALOG_MUTATION_LOCK_TIMEOUT_S", 5.0, lo=0.05, hi=60.0
    )
    timeout = max(0.01, float(timeout))
    if not process_lock.acquire(timeout=timeout):
        raise RuntimeError(f"CATALOG_MUTATION_LOCK_TIMEOUT:{catalog_path}")
    handle: Any = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+b")
        if _fcntl is not None:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f"CATALOG_MUTATION_LOCK_TIMEOUT:{catalog_path}") from exc
                    time.sleep(0.02)
        return CatalogMutationLock(lock_path=lock_path, process_lock=process_lock, handle=handle)
    except Exception:
        if handle is not None:
            handle.close()
        process_lock.release()
        raise


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def scope_segment(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"{field.upper()}_REQUIRED")
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise RuntimeError(f"INVALID_{field.upper()}")
    return text


def runtime_environment(value: str | None = None) -> str:
    text = str(value or env_str("APP_ENV", env_str("ENV", "dev")) or "dev").strip().lower()
    if text == "production":
        return "prod"
    if text == "development":
        return "dev"
    return text or "dev"


def canonical_catalog_path(
    *,
    tenant_id: str,
    product_id: str,
    environment: str | None = None,
    catalog_root: Path | None = None,
) -> Path:
    tenant = scope_segment(tenant_id, field="tenant_id")
    product = scope_segment(product_id, field="product_id")
    env = scope_segment(runtime_environment(environment), field="environment")
    repo_root = Path(__file__).resolve().parents[2]
    root = (
        catalog_root
        or env_path("OFFER_CATALOGS_DATA_DIR", str(repo_root / "data" / "offer_catalogs"))
    ).expanduser().resolve()
    path = (root / tenant / product / f"{env}.yaml").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("CATALOG_PATH_ESCAPES_ROOT") from exc
    return path


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to persist offer catalogs") from exc
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def atomic_replace_bytes(path: Path, raw: bytes, *, suffix: str = ".write.tmp", invalidate: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + suffix)
    temp.unlink(missing_ok=True)
    try:
        temp.write_bytes(raw)
        temp.replace(path)
        if invalidate:
            invalidate_yaml_cache(path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def restore_optional_bytes(path: Path, raw: bytes | None, *, suffix: str = ".restore.tmp") -> None:
    if raw is None:
        path.unlink(missing_ok=True)
        invalidate_yaml_cache(path)
        return
    atomic_replace_bytes(path, raw, suffix=suffix)


@dataclass
class CatalogMutationTransaction:
    catalog_path: Path
    catalog_tmp: Path
    original_catalog: bytes
    original_digest: str
    prepared_digest: str
    mutation_lock: CatalogMutationLock
    result: dict[str, Any] = field(default_factory=dict)
    error_prefix: str = "OFFER_CATALOG"
    applied: bool = False
    finalized: bool = False

    def _code(self, suffix: str) -> str:
        return f"{self.error_prefix}_{suffix}"

    def apply(self) -> dict[str, Any]:
        if self.finalized:
            raise RuntimeError(self._code("TRANSACTION_FINALIZED"))
        if self.applied:
            return dict(self.result)
        if file_digest(self.catalog_path) != self.original_digest:
            raise RuntimeError(self._code("CONCURRENT_MODIFICATION"))
        try:
            self.catalog_tmp.replace(self.catalog_path)
            self.applied = True
            if file_digest(self.catalog_path) != self.prepared_digest:
                raise RuntimeError(self._code("COMMIT_DIGEST_MISMATCH"))
            invalidate_yaml_cache(self.catalog_path)
        except Exception as exc:
            try:
                if self.applied:
                    self.rollback()
            except Exception as rollback_exc:
                raise RuntimeError(
                    f"{self._code('ROLLBACK_FAILED')}:{rollback_exc.__class__.__name__}:{rollback_exc}"
                ) from exc
            if isinstance(exc, RuntimeError) and str(exc).startswith(f"{self.error_prefix}_"):
                raise
            raise RuntimeError(f"{self._code('COMMIT_FAILED')}:{exc.__class__.__name__}:{exc}") from exc
        return dict(self.result)

    def rollback(self) -> None:
        if self.finalized:
            raise RuntimeError(self._code("TRANSACTION_FINALIZED"))
        if self.applied:
            if file_digest(self.catalog_path) != self.prepared_digest:
                raise RuntimeError(self._code("ROLLBACK_CONFLICT"))
            atomic_replace_bytes(
                self.catalog_path,
                self.original_catalog,
                suffix=".rollback.tmp",
            )
            if file_digest(self.catalog_path) != self.original_digest:
                raise RuntimeError(self._code("ROLLBACK_DIGEST_MISMATCH"))
            self.applied = False
        self._cleanup_temps()

    def finalize(self) -> None:
        if self.finalized:
            return
        try:
            self._cleanup_temps()
        finally:
            self.mutation_lock.release()
            self.finalized = True

    def _cleanup_temps(self) -> None:
        self.catalog_tmp.unlink(missing_ok=True)
        self.catalog_path.with_suffix(self.catalog_path.suffix + ".rollback.tmp").unlink(missing_ok=True)


def build_locked_transaction(
    *,
    catalog_path: Path,
    prepared_bytes: bytes,
    original_catalog: bytes,
    mutation_lock: CatalogMutationLock,
    tmp_suffix: str,
    error_prefix: str,
    result: dict[str, Any] | None = None,
) -> CatalogMutationTransaction:
    path = catalog_path.expanduser().resolve()
    if mutation_lock.released:
        raise RuntimeError("CATALOG_MUTATION_LOCK_RELEASED")
    tmp = path.with_suffix(path.suffix + tmp_suffix)
    try:
        tmp.unlink(missing_ok=True)
        tmp.write_bytes(prepared_bytes)
        return CatalogMutationTransaction(
            catalog_path=path,
            catalog_tmp=tmp,
            original_catalog=bytes(original_catalog),
            original_digest=digest_bytes(original_catalog),
            prepared_digest=file_digest(tmp),
            mutation_lock=mutation_lock,
            result=dict(result or {}),
            error_prefix=str(error_prefix or "OFFER_CATALOG").strip() or "OFFER_CATALOG",
        )
    except Exception:
        tmp.unlink(missing_ok=True)
        mutation_lock.release()
        raise


def prepare_bytes_transaction(
    *,
    catalog_path: Path,
    prepared_bytes: bytes,
    tmp_suffix: str,
    error_prefix: str,
    result: dict[str, Any] | None = None,
    lock_timeout_s: float | None = None,
) -> CatalogMutationTransaction:
    path = catalog_path.expanduser().resolve()
    mutation_lock = acquire_catalog_lock(path, timeout_s=lock_timeout_s)
    tmp = path.with_suffix(path.suffix + tmp_suffix)
    try:
        if not path.exists():
            raise RuntimeError(f"OFFER_CATALOG_NOT_FOUND:{path}")
        original = path.read_bytes()
        original_digest = digest_bytes(original)
        tmp.unlink(missing_ok=True)
        tmp.write_bytes(prepared_bytes)
        return CatalogMutationTransaction(
            catalog_path=path,
            catalog_tmp=tmp,
            original_catalog=original,
            original_digest=original_digest,
            prepared_digest=file_digest(tmp),
            mutation_lock=mutation_lock,
            result=dict(result or {}),
            error_prefix=str(error_prefix or "OFFER_CATALOG").strip() or "OFFER_CATALOG",
        )
    except Exception:
        tmp.unlink(missing_ok=True)
        mutation_lock.release()
        raise


__all__ = [
    "CANON_OFFER_CATALOG_MUTATION_OWNER",
    "CatalogMutationLock",
    "CatalogMutationTransaction",
    "acquire_catalog_lock",
    "atomic_replace_bytes",
    "build_locked_transaction",
    "canonical_catalog_path",
    "digest_bytes",
    "dump_yaml",
    "file_digest",
    "prepare_bytes_transaction",
    "restore_optional_bytes",
    "runtime_environment",
    "scope_segment",
]
