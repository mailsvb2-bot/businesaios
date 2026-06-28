"""Runtime assertions that hard-fail on side-effect bypass.

Single source of truth lives in runtime.executor.
This module remains as a stable import path for effects implementations.
"""

from __future__ import annotations

from runtime.executor import assert_called_from_executor as assert_called_from_executor

__all__ = ["assert_called_from_executor"]
