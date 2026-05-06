from __future__ import annotations

"""Backward compatible shim.

Canonical tracing lives in runtime/observability/tracing.py.
This module remains to avoid breaking external imports.
"""

from runtime.observability.tracing import (
    get_correlation_key as get_current_correlation_key,
    reset_correlation_key as reset_current_correlation_key,
    set_correlation_key as set_current_correlation_key,
)

