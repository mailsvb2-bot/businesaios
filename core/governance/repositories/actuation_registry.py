from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class ControllerRef:
    domain: str
    controller_id: str
    source: str


class SplitBrainActuationError(RuntimeError):
    pass


class ActuationRegistry:
    """Runtime enforcement: each side-effect domain must have exactly one executor.

    The registry stays tiny and deterministic: normalize inputs, deduplicate exact
    re-registration, expose snapshot/reset for tests and boot hygiene, and fail closed
    when domain/controller metadata is incomplete.
    """

    _lock: Lock = Lock()
    _by_domain: dict[str, list[ControllerRef]] = {}

    @classmethod
    def register(cls, *, domain: str, controller_id: str, source: str) -> None:
        ref = cls._normalize_ref(domain=domain, controller_id=controller_id, source=source)
        with cls._lock:
            refs = cls._by_domain.setdefault(ref.domain, [])
            if ref in refs:
                return
            refs.append(ref)

    @classmethod
    def assert_single_executor(cls, *, domain: str) -> None:
        normalized_domain = cls._normalize_domain(domain)
        with cls._lock:
            refs = list(cls._by_domain.get(normalized_domain, []))
        if len(refs) <= 1:
            return
        msg = 'Split-brain actuation detected:\n' + '\n'.join(
            [f'- domain={r.domain} controller={r.controller_id} source={r.source}' for r in refs]
        )
        raise SplitBrainActuationError(msg)

    @classmethod
    def snapshot(cls) -> dict[str, tuple[ControllerRef, ...]]:
        with cls._lock:
            return {domain: tuple(refs) for domain, refs in cls._by_domain.items()}

    @classmethod
    def reset(cls, *, domain: str | None = None) -> None:
        with cls._lock:
            if domain is None:
                cls._by_domain.clear()
                return
            cls._by_domain.pop(cls._normalize_domain(domain), None)

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        normalized = str(domain or '').strip()
        if not normalized:
            raise SplitBrainActuationError('domain is required')
        return normalized

    @classmethod
    def _normalize_ref(cls, *, domain: str, controller_id: str, source: str) -> ControllerRef:
        normalized_domain = cls._normalize_domain(domain)
        normalized_controller = str(controller_id or '').strip()
        normalized_source = str(source or '').strip()
        if not normalized_controller:
            raise SplitBrainActuationError(f'controller_id is required for domain {normalized_domain!r}')
        if not normalized_source:
            raise SplitBrainActuationError(f'source is required for domain {normalized_domain!r}')
        return ControllerRef(
            domain=normalized_domain,
            controller_id=normalized_controller,
            source=normalized_source,
        )
