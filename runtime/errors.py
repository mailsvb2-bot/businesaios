from __future__ import annotations

class RuntimeErrorBase(Exception):
    """Base class for runtime composition errors."""


class RuntimeConfigurationError(RuntimeErrorBase):
    """Invalid runtime configuration or boot topology."""


class RuntimeDuplicateServiceError(RuntimeErrorBase):
    """Same runtime service name was registered more than once."""


class RuntimeMissingServiceError(RuntimeErrorBase):
    """A required runtime service is missing."""


class RuntimeMissingDependencyError(RuntimeErrorBase):
    """A runtime service dependency is missing."""


class RuntimeRegistrySealedError(RuntimeErrorBase):
    """Registry is sealed and cannot be mutated."""


class RuntimeIllegalServiceTypeError(RuntimeErrorBase):
    """Attempt to register service under illegal runtime type."""
