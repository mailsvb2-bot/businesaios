"""Rate limiting primitives for Telegram outbound delivery.

Kept tiny and testable. Implementation is centralized in
`core.ratelimit.token_bucket` to avoid infrastructure duplication.
"""

from __future__ import annotations

from core.ratelimit.token_bucket import SyncTokenBucket


class TokenBucket(SyncTokenBucket):
    """Backward-compatible alias used by outbound queue."""

