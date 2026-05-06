from __future__ import annotations

"""Key management helpers.

This module provides entropy-safe rotation utilities. It does not perform IO by itself;
callers inject persistence via a `store` callable.
"""

import secrets
from typing import Callable

from core.security.keyring import Keyring


def rotate_key(*, store: Callable[[str], None]) -> str:
    """Generate a new random signing key (hex) and persist it via `store`."""
    new_key = secrets.token_hex(32)
    store(str(new_key))
    return str(new_key)


def rotate_keyring(*, keyring: Keyring, new_kid: str, store: Callable[[str, bytes], None] | None = None) -> str:
    """Rotate Keyring active key using cryptographic entropy."""
    secret_hex = secrets.token_hex(32)
    secret_bytes = secret_hex.encode("utf-8")
    keyring.rotate(str(new_kid), secret_bytes)
    if store is not None:
        store(str(new_kid), secret_bytes)
    return str(new_kid)
