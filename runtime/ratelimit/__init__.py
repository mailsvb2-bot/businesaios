from __future__ import annotations

"""Canonical runtime package alias namespace for runtime.ratelimit public API."""

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'MemoryRateLimitStore': ('core.ratelimit.token_bucket', 'MemoryRateLimitStore'),
    'RateLimitDecision': ('core.ratelimit.token_bucket', 'RateLimitDecision'),
    'RateLimitKey': ('core.ratelimit.token_bucket', 'RateLimitKey'),
    'RateLimitPolicy': ('core.ratelimit.token_bucket', 'RateLimitPolicy'),
    'TokenBucketLimiter': ('core.ratelimit.token_bucket', 'TokenBucketLimiter'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
