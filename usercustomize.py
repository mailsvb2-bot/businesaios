"""User-level Python startup hook kept intentionally inert.

Explicit application entrypoints own startup barriers and runtime validation;
implicit interpreter startup must remain lightweight and side-effect free.
"""
from __future__ import annotations
CANON_LIGHTWEIGHT_USERCUSTOMIZE = True
