"""Compatibility surface for the canonical messaging inbound owner lock.

Decision-owner policy and validation live only in
``runtime.messaging.inbound_owner_lock``. Historical imports keep the same
function and exception names without maintaining a second authority table.
"""

from __future__ import annotations

from runtime.messaging.inbound_owner_lock import (
    InboundOwnerViolation,
    assert_inbound_decision_owner as assert_inbound_owner,
)

CANON_MESSAGING_INBOUND_STRICT_COMPAT_SURFACE = True

__all__ = ["InboundOwnerViolation", "assert_inbound_owner"]
