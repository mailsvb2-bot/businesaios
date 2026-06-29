"""Canonical runtime infrastructure contract.

This root-level module defines the immutable data contract passed into runtime
execution. It must stay a passive structure only: no boot logic, no decision
logic, and no alternate wiring path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANON_RUNTIME_INFRA_CONTRACT = True
CANON_RUNTIME_INFRA_DATA_ONLY = True
CANON_RUNTIME_INFRA_NO_DECISION_LOGIC = True


@dataclass(frozen=True)
class RuntimeInfra:
    event_store: Any = None
    ledger: Any = None
    snapshot_store: Any = None
    outbox: Any = None
    payment_outbox: Any = None
    settings_gateway: Any = None
    decision_archive: Any = None
    messaging_policy_event_store: Any = None
    messaging_policy_read_service: Any = None
    http_transport: Any = None
    effect_router: Any = None
    tenant_registry: Any = None
    tenant_policy_store: Any = None
    tenant_quota_guard: Any = None
    tenant_runtime_isolation: Any = None
    tenant_execution_budget_guard: Any = None
    tenant_runtime_lease_store: Any = None
    tenant_admission_backend: Any = None
    tenant_runtime_reconciler: Any = None
    tenant_runtime_fencing_registry: Any = None
    tenant_metrics_store: Any = None
    tenant_migration_lock_backend: Any = None
    runtime_observability: Any = None
    api_security_owner_bundle: Any = None

    @property
    def decision_ledger(self):
        return self.ledger

    @property
    def snapshot_archive(self):
        return self.snapshot_store

    @property
    def effect_outbox(self):
        return self.outbox

    @property
    def payments_outbox(self):
        return self.payment_outbox

    @property
    def settings_store(self):
        return self.settings_gateway

    @property
    def messaging_policy_store(self):
        return self.messaging_policy_event_store

    @property
    def messaging_policy_reader(self):
        return self.messaging_policy_read_service

    @property
    def archive_store(self):
        return self.decision_archive


__all__ = [
    "CANON_RUNTIME_INFRA_CONTRACT",
    "CANON_RUNTIME_INFRA_DATA_ONLY",
    "CANON_RUNTIME_INFRA_NO_DECISION_LOGIC",
    "RuntimeInfra",
]
