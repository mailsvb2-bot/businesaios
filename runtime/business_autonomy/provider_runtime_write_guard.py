from __future__ import annotations

"""Fail-closed provider runtime write guard.

This module is not a second decision brain.  It derives operation class from the
canonical ProviderSyncRuntimePlanner and readiness truth from the canonical
provider truth matrix.  It only answers whether a provider runtime operation is
allowed to continue in live mode.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_truth_matrix import ProviderTruthRow, provider_truth_map
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner

CANON_PROVIDER_RUNTIME_WRITE_GUARD = True
PROVIDER_WRITE_BLOCK_STATUS = "rejected_provider_write_guard"


@dataclass(frozen=True)
class ProviderRuntimeWriteGuardDecision:
    provider_key: str
    operation: str
    mode: str
    is_write_operation: bool
    allowed: bool
    status: str
    reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "provider_key": self.provider_key,
            "operation": self.operation,
            "mode": self.mode,
            "is_write_operation": self.is_write_operation,
            "allowed": self.allowed,
            "status": self.status,
            "reason": self.reason,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class ProviderRuntimeWriteGuard:
    planner: ProviderSyncRuntimePlanner = field(default_factory=ProviderSyncRuntimePlanner)

    def evaluate(self, *, provider: ProviderDefinition, operation: str, mode: str) -> ProviderRuntimeWriteGuardDecision:
        normalized_mode = str(mode or "dry_run").strip().lower() or "dry_run"
        normalized_operation = str(operation or "").strip()
        plan = self.planner.describe(provider)
        truth = provider_truth_map().get(provider.provider_key)
        is_write = normalized_operation in set(plan.write_operations)
        base_metadata = {
            "truth_source": "application.business_autonomy.provider_truth_matrix",
            "planner_source": "runtime.business_autonomy.provider_sync_runtime.ProviderSyncRuntimePlanner",
            "read_operations": list(plan.read_operations),
            "write_operations": list(plan.write_operations),
            "truth": {} if truth is None else self._truth_metadata(truth),
        }
        if normalized_mode != "live":
            return ProviderRuntimeWriteGuardDecision(
                provider_key=provider.provider_key,
                operation=normalized_operation,
                mode=normalized_mode,
                is_write_operation=is_write,
                allowed=True,
                status="allowed_non_live_mode",
                reason="non_live_mode_is_read_only_or_prepared",
                metadata=base_metadata,
            )
        if not is_write:
            return ProviderRuntimeWriteGuardDecision(
                provider_key=provider.provider_key,
                operation=normalized_operation,
                mode=normalized_mode,
                is_write_operation=False,
                allowed=True,
                status="allowed_live_read_operation",
                reason="operation_not_in_provider_write_operations",
                metadata=base_metadata,
            )
        if truth is None:
            return ProviderRuntimeWriteGuardDecision(
                provider_key=provider.provider_key,
                operation=normalized_operation,
                mode=normalized_mode,
                is_write_operation=True,
                allowed=False,
                status=PROVIDER_WRITE_BLOCK_STATUS,
                reason="provider_truth_row_missing",
                metadata=base_metadata,
            )
        if not truth.write_supported:
            return ProviderRuntimeWriteGuardDecision(
                provider_key=provider.provider_key,
                operation=normalized_operation,
                mode=normalized_mode,
                is_write_operation=True,
                allowed=False,
                status=PROVIDER_WRITE_BLOCK_STATUS,
                reason="write_supported_false_in_provider_truth_matrix",
                metadata=base_metadata,
            )
        if truth.approval_required:
            return ProviderRuntimeWriteGuardDecision(
                provider_key=provider.provider_key,
                operation=normalized_operation,
                mode=normalized_mode,
                is_write_operation=True,
                allowed=False,
                status=PROVIDER_WRITE_BLOCK_STATUS,
                reason="approval_evidence_contract_not_wired_for_live_write",
                metadata=base_metadata,
            )
        return ProviderRuntimeWriteGuardDecision(
            provider_key=provider.provider_key,
            operation=normalized_operation,
            mode=normalized_mode,
            is_write_operation=True,
            allowed=True,
            status="allowed_live_write_operation",
            reason="provider_truth_matrix_allows_write_without_approval_requirement",
            metadata=base_metadata,
        )

    def _truth_metadata(self, truth: ProviderTruthRow) -> dict[str, Any]:
        return {
            "status": truth.status,
            "live_ready": truth.live_ready,
            "read_only_supported": truth.read_only_supported,
            "write_supported": truth.write_supported,
            "approval_required": truth.approval_required,
            "risk_level": truth.risk_level,
            "admin_visible": truth.admin_visible,
        }


__all__ = [
    "CANON_PROVIDER_RUNTIME_WRITE_GUARD",
    "PROVIDER_WRITE_BLOCK_STATUS",
    "ProviderRuntimeWriteGuard",
    "ProviderRuntimeWriteGuardDecision",
]
