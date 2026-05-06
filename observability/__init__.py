from __future__ import annotations

"""Canonical root observability facade.

The package root is the owner surface for cross-cutting observability
primitives. Historical imports from ``observability.public_api`` continue to
resolve through an explicit thin compatibility module.
"""

from importlib import import_module

from canon.public_api_alias import install_public_api_alias
from typing import Any

from observability.action_audit_log import ActionAuditLog, CANON_ACTION_AUDIT_LOG
from observability.metrics import InMemoryMetrics, CounterStore, CANON_INMEMORY_METRICS
from observability.alert_rule_contract import AlertComparator, AlertMatch, AlertRule, AlertSeverity, AlertWindow
from observability.alerting_policy import AlertingPolicy
from observability.audit_event_schema import AuditCategory, AuditEventRecord, AuditSeverity
from observability.audit_export_service import AuditExportService
from observability.immutable_event_store import CANON_IMMUTABLE_EVENT_STORE, ImmutableEventRecord, ImmutableEventStore
from observability.distributed_trace_context import CANON_DISTRIBUTED_TRACE_CONTEXT, DistributedTraceContext
from observability.decision_audit_log import DecisionAuditLog, CANON_DECISION_AUDIT_LOG
from observability.delivery_metrics import DeliveryObservabilityMetrics, CANON_DELIVERY_OBSERVABILITY_METRICS
from observability.decision_trace_store import InMemoryDecisionTraceStore, NullDecisionTraceStore, PersistentDecisionTraceStore
from observability.execution_trace_contract import DecisionTraceEvent, EffectDisposition, ExecutionTraceEvent, RuntimeEffectTraceEvent, TraceStage
from observability.execution_span import CANON_EXECUTION_SPAN, ExecutionSpan
from observability.execution_trace_store import InMemoryExecutionTraceStore, NullExecutionTraceStore, PersistentExecutionTraceStore
from observability.incident_signal_store import InMemoryIncidentSignalStore, IncidentSignalRecord, IncidentStatus, PersistentIncidentSignalStore
from observability.runtime_effect_trace_store import InMemoryRuntimeEffectTraceStore, NullRuntimeEffectTraceStore, PersistentRuntimeEffectTraceStore
from observability.runtime_trace_graph import CANON_RUNTIME_TRACE_GRAPH, RuntimeTraceGraph, RuntimeTraceGraphBuilder
from observability.sli_collector import SLICollector
from observability.slo_contract import SLIKind, SLIReading, SLOComparator, SLODefinition, SLOEvaluation
from observability.tenant_metrics_registry import MetricAggregation, MetricSample, TenantMetricsRegistry
from observability.metrics_exporter import MetricsExporter
from observability.security_audit_log import CANON_SECURITY_AUDIT_LOG, SecurityAuditLog
from observability.platform.decision_audit.jsonl_store import CANON_DECISION_AUDIT_JSONL_STORE, DecisionAuditEvent, JsonlDecisionAuditStore
from observability.platform.logging import CANON_PLATFORM_LOGGING_PUBLIC_API, get_logger, log_kv
from observability.platform.telemetry.event_store import (
    CANON_PLATFORM_TELEMETRY_EVENT_STORE,
    CANON_PLATFORM_TELEMETRY_EVENT_STREAM,
    EventStore,
    EventStoreSink,
    InMemoryEventStore,
    JsonlEventStore,
    SqliteEventStore,
    build_default_event_store,
)
from observability.trace_exporter import TraceExporter
from observability.tracing import TraceSpan, start_span
from observability.inference_budget_burn_log import InferenceBudgetBurnEvent, InferenceBudgetBurnLog
from observability.inference_capacity_trace_store import InferenceCapacityTrace, InferenceCapacityTraceStore
from observability.inference_escalation_audit_log import InferenceEscalationAuditEvent, InferenceEscalationAuditLog
from observability.inference_provider_health_log import InferenceProviderHealthEvent, InferenceProviderHealthLog
from observability.inference_runtime_summary import InferenceRuntimeSummaryService
from observability.inference_verification_log import InferenceVerificationEvent, InferenceVerificationLog
from observability.inference_acceleration_log import InferenceAccelerationEvent, InferenceAccelerationLog

CANON_OBSERVABILITY_PUBLIC_API = True
CANON_OBSERVABILITY_PACKAGE_OWNER = True

_CATALOG_EXPORTS = {
    'ExecutionMetrics',
    'ExperimentMetrics',
    'LeadMetrics',
    'MagicMomentEvents',
    'OBSERVABILITY_COMPAT_EXPORTS',
    'PlatformMetrics',
    'RevenueMetrics',
    'SeoMetrics',
    'emit',
}


def __getattr__(name: str) -> Any:
    if name in _CATALOG_EXPORTS:
        catalog = import_module('observability.catalog')
        value = getattr(catalog, name)
        globals()[name] = value
        return value
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def log_audit(logger_name: str, message: str, **fields: object) -> None:
    logger = get_logger(str(logger_name))
    log_kv(logger, message, **fields)


install_public_api_alias(__name__)

__all__ = [
    "ActionAuditLog",
    "AlertComparator",
    "AlertMatch",
    "AlertRule",
    "AlertSeverity",
    "AlertWindow",
    "AlertingPolicy",
    "AuditCategory",
    "AuditEventRecord",
    "AuditExportService",
    "AuditSeverity",
    "CANON_ACTION_AUDIT_LOG",
    "CANON_DECISION_AUDIT_JSONL_STORE",
    "CANON_DISTRIBUTED_TRACE_CONTEXT",
    "CANON_DECISION_AUDIT_LOG",
    "CANON_DELIVERY_OBSERVABILITY_METRICS",
    "CANON_EXECUTION_SPAN",
    "CANON_IMMUTABLE_EVENT_STORE",
    "CANON_INMEMORY_METRICS",
    "CANON_OBSERVABILITY_PACKAGE_OWNER",
    "CANON_OBSERVABILITY_PUBLIC_API",
    "CANON_RUNTIME_TRACE_GRAPH",
    "CANON_PLATFORM_LOGGING_PUBLIC_API",
    "CANON_PLATFORM_TELEMETRY_EVENT_STORE",
    "CANON_PLATFORM_TELEMETRY_EVENT_STREAM",
    "CANON_SECURITY_AUDIT_LOG",
    "CounterStore",
    "build_default_event_store",
    "DecisionAuditEvent",
    "DeliveryObservabilityMetrics",
    "DecisionAuditLog",
    "DistributedTraceContext",
    "DecisionTraceEvent",
    "EffectDisposition",
    "ExecutionMetrics",
    "ExecutionSpan",
    "EventStore",
    "EventStoreSink",
    "ExecutionTraceEvent",
    "ExperimentMetrics",
    "InMemoryDecisionTraceStore",
    "InMemoryEventStore",
    "InMemoryExecutionTraceStore",
    "InMemoryIncidentSignalStore",
    "InMemoryMetrics",
    "ImmutableEventRecord",
    "ImmutableEventStore",
    "InferenceVerificationLog",
    "InferenceAccelerationEvent",
    "InferenceAccelerationLog",
    "InferenceVerificationEvent",
    "InferenceRuntimeSummaryService",
    "InferenceProviderHealthLog",
    "InferenceProviderHealthEvent",
    "InferenceEscalationAuditLog",
    "InferenceEscalationAuditEvent",
    "InferenceCapacityTraceStore",
    "InferenceCapacityTrace",
    "InferenceBudgetBurnEvent",
    "InferenceBudgetBurnLog",
    "InMemoryRuntimeEffectTraceStore",
    "IncidentSignalRecord",
    "IncidentStatus",
    "JsonlDecisionAuditStore",
    "JsonlEventStore",
    "LeadMetrics",
    "SqliteEventStore",
    "MetricAggregation",
    "MetricSample",
    "MagicMomentEvents",
    "MetricsExporter",
    "OBSERVABILITY_COMPAT_EXPORTS",
    "NullDecisionTraceStore",
    "NullExecutionTraceStore",
    "NullRuntimeEffectTraceStore",
    "PlatformMetrics",
    "PersistentDecisionTraceStore",
    "PersistentExecutionTraceStore",
    "PersistentIncidentSignalStore",
    "PersistentRuntimeEffectTraceStore",
    "RevenueMetrics",
    "RuntimeEffectTraceEvent",
    "RuntimeTraceGraph",
    "RuntimeTraceGraphBuilder",
    "SLICollector",
    "SLIKind",
    "SLIReading",
    "SLOComparator",
    "SLODefinition",
    "SLOEvaluation",
    "TenantMetricsRegistry",
    "SecurityAuditLog",
    "SeoMetrics",
    "TraceExporter",
    "TraceSpan",
    "TraceStage",
    "get_logger",
    "log_audit",
    "log_kv",
    "emit",
    "start_span",
]

