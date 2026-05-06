from __future__ import annotations

from runtime.manifest_entry import RuntimeManifestEntry
from runtime.registration_result import RegistrationResult
from runtime.registry import RuntimeRegistry


class RuntimeRegistrationInvoker:
    def __init__(self, resolver: "RuntimeDependencyResolver") -> None:
        self._resolver = resolver

    def invoke(
        self,
        entry: RuntimeManifestEntry,
        registry: RuntimeRegistry,
    ) -> RegistrationResult:
        register_callable = self._resolver.resolve_callable(
            entry.module_path,
            entry.callable_name,
        )
        result = register_callable(registry)
        if not isinstance(result, RegistrationResult):
            raise TypeError(
                f"Runtime registration '{entry.step_name}' returned {type(result).__name__}; "
                'expected RegistrationResult.'
            )

        if result.service_name != entry.service_name:
            raise ValueError(
                f"Runtime registration mismatch for step '{entry.step_name}': "
                f"expected service '{entry.service_name}', got '{result.service_name}'."
            )

        if result.service_type != entry.service_type:
            raise ValueError(
                f"Runtime service type mismatch for service '{entry.service_name}': "
                f"expected '{entry.service_type}', got '{result.service_type}'."
            )

        if tuple(result.dependencies) != tuple(entry.dependencies):
            raise ValueError(
                f"Runtime dependency mismatch for service '{entry.service_name}'."
            )

        return result
