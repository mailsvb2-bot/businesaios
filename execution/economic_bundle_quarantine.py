from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from collections.abc import Mapping

CANON_ECONOMIC_BUNDLE_QUARANTINE = True


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class EconomicBundleQuarantineRecord:
    bundle_path: str
    reason: str
    issues: tuple[str, ...] = ()
    scope: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'bundle_path': self.bundle_path,
            'reason': self.reason,
            'issues': list(self.issues),
            'scope': dict(self.scope),
            'created_at': self.created_at,
            'metadata': dict(self.metadata),
        }


class EconomicBundleQuarantineSink(Protocol):
    def record(self, row: EconomicBundleQuarantineRecord) -> None: ...


class NoOpEconomicBundleQuarantine:
    def record(self, row: EconomicBundleQuarantineRecord) -> None:
        return None


class InMemoryEconomicBundleQuarantine:
    def __init__(self) -> None:
        self._rows: list[EconomicBundleQuarantineRecord] = []

    def record(self, row: EconomicBundleQuarantineRecord) -> None:
        self._rows.append(row)

    def list_rows(self) -> tuple[EconomicBundleQuarantineRecord, ...]:
        return tuple(self._rows)


class JsonlEconomicBundleQuarantine:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, row: EconomicBundleQuarantineRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write('\n')


def build_quarantine_record(*, bundle_path: str | Path, reason: str, issues: list[str] | tuple[str, ...] = (), scope: Mapping[str, Any] | None = None, metadata: Mapping[str, Any] | None = None) -> EconomicBundleQuarantineRecord:
    return EconomicBundleQuarantineRecord(
        bundle_path=_text(bundle_path),
        reason=_text(reason) or 'economic_bundle_quarantined',
        issues=tuple(str(item) for item in issues if _text(item)),
        scope=_safe_dict(scope),
        metadata={
            'owner': 'execution.economic_bundle_quarantine',
            **_safe_dict(metadata),
        },
    )


__all__ = [
    'CANON_ECONOMIC_BUNDLE_QUARANTINE',
    'EconomicBundleQuarantineRecord',
    'EconomicBundleQuarantineSink',
    'NoOpEconomicBundleQuarantine',
    'InMemoryEconomicBundleQuarantine',
    'JsonlEconomicBundleQuarantine',
    'build_quarantine_record',
]
