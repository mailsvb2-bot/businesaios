"""Thin public adapter for canonical Ads Apply helpers.

The implementation owner imports the public ``runtime.ads`` surface.
"""

from runtime.handler_impl.ads_apply_helpers import (
    build_apply_request,
    decode_ads_plan,
    emit_apply_audit,
    emit_apply_success_governance,
    summary_text,
)

__all__ = [
    "build_apply_request",
    "decode_ads_plan",
    "emit_apply_audit",
    "emit_apply_success_governance",
    "summary_text",
]
