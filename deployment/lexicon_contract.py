from __future__ import annotations

"""Canonical namespace contract for deployment-related surfaces.

This module does not introduce a new deploy engine. It only documents and
locks ownership so deployment semantics do not fragment across similarly named
namespaces.
"""

from dataclasses import dataclass
from pathlib import Path

CANON_DEPLOYMENT_LEXICON_CONTRACT = True


@dataclass(frozen=True)
class NamespaceRole:
    namespace: str
    role: str
    allowed_payload: tuple[str, ...]
    forbidden_payload: tuple[str, ...] = ()


DEPLOYMENT_NAMESPACE_ROLES: tuple[NamespaceRole, ...] = (
    NamespaceRole(
        namespace="deploy",
        role="host-facing install assets and operator entry scripts",
        allowed_payload=("docker", "systemd", "windows", "README", "service units"),
        forbidden_payload=("decision policy", "runtime business logic", "python release state owners"),
    ),
    NamespaceRole(
        namespace="deployment",
        role="canonical Python deployment/release/readiness/state owners",
        allowed_payload=("readiness", "migration guards", "release audit", "version manifests", "deploy state store"),
        forbidden_payload=("decision issuance", "runtime execution path", "UI rendering"),
    ),
    NamespaceRole(
        namespace="infra",
        role="runtime governance / ops support contracts and services",
        allowed_payload=("approval", "audit", "rollback packets", "runtime guardrails"),
        forbidden_payload=("host manifests", "docker/systemd installers"),
    ),
    NamespaceRole(
        namespace="infrastructure",
        role="host / cluster assets and low-level ops materials",
        allowed_payload=("k8s", "firewall", "secrets runtime assets", "observability infra assets"),
        forbidden_payload=("python deploy state owners", "runtime decision logic"),
    ),
    NamespaceRole(
        namespace="runtime.bootstrap",
        role="canonical sovereign bootstrap implementation owner",
        allowed_payload=("contracts", "wiring", "composition", "attestation", "validators"),
        forbidden_payload=("secondary bootstrap path", "CRM compat public surface expansion"),
    ),
    NamespaceRole(
        namespace="runtime.bootstrap",
        role="thin compatibility/public bootstrap surface only",
        allowed_payload=("explicit re-exports", "lazy public package surface", "compat shims"),
        forbidden_payload=("new owner logic", "duplicate bootstrap orchestration", "wildcard re-exports"),
    ),
)


def deployment_namespace_map() -> dict[str, NamespaceRole]:
    return {item.namespace: item for item in DEPLOYMENT_NAMESPACE_ROLES}


def detect_deployment_namespace(root: str | Path) -> dict[str, bool]:
    repo_root = Path(root)
    return {
        item.namespace: (repo_root / item.namespace.replace('.', '/')).exists()
        for item in DEPLOYMENT_NAMESPACE_ROLES
    }


__all__ = [
    'CANON_DEPLOYMENT_LEXICON_CONTRACT',
    'DEPLOYMENT_NAMESPACE_ROLES',
    'NamespaceRole',
    'deployment_namespace_map',
    'detect_deployment_namespace',
]
