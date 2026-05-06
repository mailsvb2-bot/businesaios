from __future__ import annotations

from dataclasses import dataclass


RUNTIME_DECISION_SERVICE_CONTRACT_VERSION = "RDS-CONTRACT-V1"
CANON_RUNTIME_DECISION_SERVICE_DESCRIPTOR_OWNER = True


@dataclass(frozen=True)
class DecisionServiceDescriptor:
    service_name: str
    domain: str
    source: str = "DecisionCore"


def build_decision_service_descriptor(
    *,
    domain: str,
    service_name: str = "decision_gateway",
    source: str = "DecisionCore",
) -> DecisionServiceDescriptor:
    return DecisionServiceDescriptor(service_name=service_name, domain=domain, source=source)


__all__ = [
    "CANON_RUNTIME_DECISION_SERVICE_DESCRIPTOR_OWNER",
    "RUNTIME_DECISION_SERVICE_CONTRACT_VERSION",
    "DecisionServiceDescriptor",
    "build_decision_service_descriptor",
]
