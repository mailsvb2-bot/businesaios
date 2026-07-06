from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from interfaces.common.connector_capabilities import ConnectorCapabilities

CANON_ADS_CAPABILITIES = True


@dataclass(frozen=True)
class AdsCapabilities:
    read_inventory: bool = True
    read_metrics: bool = True
    write_campaigns: bool = False
    write_budgets: bool = False
    write_bids: bool = False
    write_creatives: bool = False
    verify_writes: bool = False
    dry_run: bool = False
    idempotent: bool = False
    requires_human_approval: bool = True
    production_ready: bool = False
    demo: bool = False
    operation_names: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ops = tuple(sorted({str(item).strip() for item in self.operation_names if str(item).strip()}))
        object.__setattr__(self, 'operation_names', ops)
        if self.production_ready and self.demo:
            raise ValueError('non-live demo connector cannot be production_ready')
        if self.production_ready and self.supports_write and not self.verify_writes:
            raise ValueError('production-ready write connectors must support verify_writes')

    @property
    def supports_read(self) -> bool:
        return bool(self.read_inventory or self.read_metrics)

    @property
    def supports_write(self) -> bool:
        return bool(self.write_campaigns or self.write_budgets or self.write_bids or self.write_creatives)

    def as_dict(self) -> dict[str, Any]:
        return {
            'read_inventory': bool(self.read_inventory),
            'read_metrics': bool(self.read_metrics),
            'write_campaigns': bool(self.write_campaigns),
            'write_budgets': bool(self.write_budgets),
            'write_bids': bool(self.write_bids),
            'write_creatives': bool(self.write_creatives),
            'verify_writes': bool(self.verify_writes),
            'dry_run': bool(self.dry_run),
            'idempotent': bool(self.idempotent),
            'requires_human_approval': bool(self.requires_human_approval),
            'production_ready': bool(self.production_ready),
            'demo': bool(self.demo),
            'supports_read': self.supports_read,
            'supports_write': self.supports_write,
            'operation_names': list(self.operation_names),
            'metadata': dict(self.metadata),
        }

    def to_connector_capabilities(self) -> ConnectorCapabilities:
        metadata = dict(self.metadata)
        metadata.setdefault('production_ready', bool(self.production_ready))
        metadata.setdefault('demo', bool(self.demo))
        metadata.setdefault('operation_names', list(self.operation_names))
        return ConnectorCapabilities(
            read=self.supports_read,
            write=self.supports_write,
            verify=bool(self.verify_writes),
            dry_run=bool(self.dry_run),
            idempotent=bool(self.idempotent),
            requires_human_approval=bool(self.requires_human_approval),
            metadata=metadata,
        )

    @classmethod
    def from_registry_entry(cls, entry: Mapping[str, Any]) -> AdsCapabilities:
        actions = tuple(str(item).strip() for item in entry.get('action_types') or () if str(item).strip())
        return cls(
            read_inventory=bool(entry.get('read', False)),
            read_metrics=bool(entry.get('read', False)),
            write_campaigns=bool(entry.get('write', False)),
            verify_writes=bool(entry.get('verify', False)),
            dry_run=bool(entry.get('supports_dry_run', False)),
            idempotent=bool(entry.get('supports_idempotency', False)),
            requires_human_approval=bool(entry.get('requires_human_approval', True)),
            production_ready=bool(entry.get('production_ready', False)),
            demo=bool(entry.get('demo', False)),
            operation_names=actions,
            metadata={'status': str(entry.get('status') or ''), 'implemented': bool(entry.get('implemented', False))},
        )


__all__ = ['AdsCapabilities', 'CANON_ADS_CAPABILITIES']
