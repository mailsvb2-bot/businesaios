from typing import Protocol


class SecretProvider(Protocol):
    """SecretProvider is an infra-only capability.

    Invariant:
      Secrets NEVER cross the Decision Boundary.

    Core code may depend on this *interface* for typing, but must never
    import any concrete implementation or access secrets directly.
    """

    def get(self, key: str) -> str:
        ...
