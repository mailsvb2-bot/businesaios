"""Infrastructure secret adapters.

This package remains an infra-only boundary. Runtime env access stays the
historical entrypoint, while the canonical ``security`` namespace provides the
shared contracts and vault primitives behind it.
"""

from infrastructure.secrets.runtime import get_secret, register_runtime_secret

__all__ = ['get_secret', 'register_runtime_secret']
