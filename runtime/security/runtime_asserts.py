from __future__ import annotations

"""Runtime assertions that hard-fail on side-effect bypass.

Single source of truth lives in runtime.executor.
This module remains as a stable import path for effects implementations.
"""

from runtime.executor import assert_called_from_executor
