"""Connector platform primitives.

Infra-only connector framework. This namespace must stay subordinate to the
single canonical execution path and must not introduce business decision logic.
"""

from connectors.platform.connector_capability_contract import (
    CANON_CONNECTOR_CAPABILITY_CONTRACT,
    ConnectorCapabilityDescriptor,
    ConnectorMaturity,
)
from connectors.platform.connector_contract import (
    BaseConnectorPlatformAdapter,
    CANON_PLATFORM_CONNECTOR_CONTRACT,
    ConnectorRequest,
    ConnectorVerificationRequest,
    PlatformConnector,
)
from connectors.platform.connector_circuit_breaker import (
    CANON_CONNECTOR_CIRCUIT_BREAKER,
    BreakerPermit,
    BreakerState,
    CircuitBreakerRule,
    CircuitBreakerSnapshot,
    ConnectorCircuitBreaker,
)
from connectors.platform.connector_failover_router import (
    CANON_CONNECTOR_FAILOVER_ROUTER,
    ConnectorFailoverResult,
    ConnectorFailoverRouter,
    ConnectorRouteAttempt,
)
from connectors.platform.connector_retry_policy import (
    CANON_CONNECTOR_RETRY_POLICY,
    ConnectorRetryPolicy,
    ConnectorRetryRule,
    RetryClassification,
    RetryContext,
)
from connectors.platform.connector_fallback_router import (
    CANON_CONNECTOR_FALLBACK_ROUTER,
    ConnectorFallbackRouter,
    FallbackRoute,
)
from connectors.platform.connector_health_monitor import (
    CANON_CONNECTOR_HEALTH_MONITOR,
    ConnectorHealthMonitor,
    ConnectorHealthSample,
    ConnectorHealthVerdict,
)
from connectors.platform.connector_observability import (
    CANON_CONNECTOR_OBSERVABILITY,
    ConnectorExecutionEvent,
    ConnectorObservability,
)
from connectors.platform.connector_quota_guard import (
    CANON_CONNECTOR_QUOTA_GUARD,
    ConnectorQuotaGuard,
    ConnectorQuotaVerdict,
)
from connectors.platform.connector_registry import (
    CANON_CONNECTOR_REGISTRY,
    ConnectorRegistry,
    ConnectorRegistryEntry,
)
from connectors.platform.connector_sandbox import (
    CANON_CONNECTOR_SANDBOX,
    ConnectorSandbox,
    ConnectorSandboxPolicy,
)
from connectors.platform.connector_secret_binding import (
    CANON_CONNECTOR_SECRET_BINDING,
    ConnectorSecretBinding,
    ConnectorSecretBindingResolver,
)
from connectors.platform.connector_timeout_policy import (
    CANON_CONNECTOR_TIMEOUT_POLICY,
    ConnectorTimeoutPolicy,
    ConnectorTimeoutRule,
    TimeoutDecision,
)
from connectors.platform.connector_version_registry import (
    CANON_CONNECTOR_VERSION_REGISTRY,
    ConnectorVersionRecord,
    ConnectorVersionRegistry,
)

__all__ = [name for name in globals() if name.startswith('CANON_') or not name.startswith('_')]
