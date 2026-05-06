"""Common connector contracts and helpers."""

from .connector_capabilities import ConnectorCapabilities
from .registry_capability_contract import RegistryCapabilityEntry, build_registry_entry

__all__ = [
    "ConnectorCapabilities",
    "RegistryCapabilityEntry",
    "build_registry_entry",
]
