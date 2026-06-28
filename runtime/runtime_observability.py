from __future__ import annotations

from dataclasses import dataclass
from runtime.audit_log import RuntimeAuditLog

"""Canonical runtime observability owner.

This module is allowed to append audit-style runtime observability events only.
It must not become a decision surface, runtime assembler, or hidden side-effect
router.
"""

CANON_RUNTIME_OBSERVABILITY_OWNER = True
CANON_RUNTIME_OBSERVABILITY_AUDIT_ONLY = True
CANON_RUNTIME_OBSERVABILITY_NO_DECISION_LOGIC = True
CANON_RUNTIME_OBSERVABILITY_ONE_TRACE_STORY = True


@dataclass
class RuntimeObservability:
    audit_log: RuntimeAuditLog

    def record_audit_event(self, event_name: str, **fields: float | int | str) -> None:
        self.audit_log.append(str(event_name), **dict(fields))

    def record_boot_started(self) -> None:
        self.record_audit_event("runtime_boot_started")

    def record_manifest_loaded(self, entries_count: int) -> None:
        self.record_audit_event(
            "runtime_manifest_loaded",
            entries_count=entries_count,
        )

    def record_manifest_validated(self) -> None:
        self.record_audit_event("runtime_manifest_validated")

    def record_registration_started(self, step_name: str, service_name: str) -> None:
        self.record_audit_event(
            "runtime_registration_started",
            step_name=step_name,
            service_name=service_name,
        )

    def record_registration_completed(
        self,
        step_name: str,
        service_name: str,
        service_type: str,
        implementation_type: str,
    ) -> None:
        self.record_audit_event(
            "runtime_registration_completed",
            step_name=step_name,
            service_name=service_name,
            service_type=service_type,
            implementation_type=implementation_type,
        )

    def record_boot_validated(self) -> None:
        self.record_audit_event("runtime_boot_validated")

    def record_registry_sealed(self) -> None:
        self.record_audit_event("runtime_registry_sealed")

    def record_model_signal(
        self,
        *,
        model_name: str,
        signal_type: str,
        source: str,
    ) -> None:
        self.record_audit_event(
            "model_signal_received",
            model_name=model_name,
            signal_type=signal_type,
            source=source,
        )

    def record_model_snapshot(
        self,
        *,
        model_name: str,
        metric_name: str,
        metric_value: float,
    ) -> None:
        self.record_audit_event(
            "model_snapshot_recorded",
            model_name=model_name,
            metric_name=metric_name,
            metric_value=metric_value,
        )

    def record_model_alert(
        self,
        *,
        model_name: str,
        code: str,
        severity: str,
        value: float,
    ) -> None:
        self.record_audit_event(
            "model_alert_recorded",
            model_name=model_name,
            code=code,
            severity=severity,
            value=value,
        )

    def record_trace_story(
        self,
        *,
        trace_name: str,
        stage: str,
        generated_at_ms: int,
        trace_kind: str,
        **fields: float | int | str,
    ) -> None:
        payload = {
            "trace_name": trace_name,
            "stage": stage,
            "generated_at_ms": int(generated_at_ms),
            "trace_kind": str(trace_kind),
        }
        payload.update(dict(fields))
        self.record_audit_event("runtime_trace_story", **payload)

    def record_world_state_trace(
        self,
        *,
        trace_name: str,
        stage: str,
        generated_at_ms: int,
        **fields: float | int | str,
    ) -> None:
        self.record_trace_story(
            trace_name=trace_name,
            stage=stage,
            generated_at_ms=generated_at_ms,
            trace_kind="world_state",
            **fields,
        )

    def record_decision_trace(
        self,
        *,
        trace_name: str,
        stage: str,
        generated_at_ms: int,
        **fields: float | int | str,
    ) -> None:
        self.record_trace_story(
            trace_name=trace_name,
            stage=stage,
            generated_at_ms=generated_at_ms,
            trace_kind="decision",
            **fields,
        )

    def record_execution_trace(
        self,
        *,
        trace_name: str,
        stage: str,
        generated_at_ms: int,
        **fields: float | int | str,
    ) -> None:
        self.record_trace_story(
            trace_name=trace_name,
            stage=stage,
            generated_at_ms=generated_at_ms,
            trace_kind="execution",
            **fields,
        )

    def record_recovery_trace(
        self,
        *,
        trace_name: str,
        stage: str,
        generated_at_ms: int,
        **fields: float | int | str,
    ) -> None:
        self.record_trace_story(
            trace_name=trace_name,
            stage=stage,
            generated_at_ms=generated_at_ms,
            trace_kind="recovery",
            **fields,
        )

    def record_effect_trace(
        self,
        *,
        trace_name: str,
        stage: str,
        generated_at_ms: int,
        **fields: float | int | str,
    ) -> None:
        self.record_trace_story(
            trace_name=trace_name,
            stage=stage,
            generated_at_ms=generated_at_ms,
            trace_kind="effect",
            **fields,
        )

    def record_advisory_packet_built(
        self,
        *,
        packet_name: str,
        recommendation_count: int,
    ) -> None:
        self.record_audit_event(
            "advisory_packet_built",
            packet_name=packet_name,
            recommendation_count=recommendation_count,
        )


__all__ = [
    "CANON_RUNTIME_OBSERVABILITY_AUDIT_ONLY",
    "CANON_RUNTIME_OBSERVABILITY_NO_DECISION_LOGIC",
    "CANON_RUNTIME_OBSERVABILITY_ONE_TRACE_STORY",
    "CANON_RUNTIME_OBSERVABILITY_OWNER",
    "RuntimeObservability",
]
