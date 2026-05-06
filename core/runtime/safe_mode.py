from __future__ import annotations

"""Process-level SAFE_MODE flag.

Constitution:
- SAFE_MODE may be entered only as a consequence of an ARCH_VIOLATION or a
  signed safe-mode decision (future extension).
- SAFE_MODE forbids irreversible side-effects except noop@v1.
"""

_SAFE_MODE: bool = False
_REASON: str | None = None

def enter_safe_mode(reason: str) -> None:
    global _SAFE_MODE, _REASON
    _SAFE_MODE = True
    _REASON = reason

def is_safe_mode() -> bool:
    return _SAFE_MODE

def reason() -> str | None:
    return _REASON


def reset_for_tests() -> None:
    global _SAFE_MODE, _REASON
    _SAFE_MODE = False
    _REASON = None
