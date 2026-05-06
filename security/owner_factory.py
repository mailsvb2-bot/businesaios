from __future__ import annotations

"""Canonical owner support for security infrastructure construction.

This module centralizes creation of the immutable security audit contour and the
single SecurityIntegrationAdapter used by higher-level boundary owners.
It prevents silent duplication of security infrastructure across API/web
surfaces while keeping the construction logic small and explicit.
"""

from dataclasses import dataclass
from pathlib import Path

from observability.immutable_event_store import ImmutableEventStore
from observability.security_audit_log import SecurityAuditLog
from security.security_integration_adapter import SecurityIntegrationAdapter
from security.security_policy_engine import SecurityPolicyEngine


CANON_SECURITY_OWNER_FACTORY = True


@dataclass(frozen=True)
class SecurityInfrastructureOwner:
    audit_path: Path
    audit_store: ImmutableEventStore
    audit_log: SecurityAuditLog
    adapter: SecurityIntegrationAdapter


def build_security_infrastructure(*, audit_path: str | Path) -> SecurityInfrastructureOwner:
    path = Path(audit_path)
    store = ImmutableEventStore(path)
    audit_log = SecurityAuditLog(store=store)
    adapter = SecurityIntegrationAdapter(
        engine=SecurityPolicyEngine(),
        audit_log=audit_log,
    )
    return SecurityInfrastructureOwner(
        audit_path=path,
        audit_store=store,
        audit_log=audit_log,
        adapter=adapter,
    )


def build_default_security_adapter(*, audit_path: str | Path) -> SecurityIntegrationAdapter:
    return build_security_infrastructure(audit_path=audit_path).adapter


__all__ = [
    'CANON_SECURITY_OWNER_FACTORY',
    'SecurityInfrastructureOwner',
    'build_default_security_adapter',
    'build_security_infrastructure',
]
