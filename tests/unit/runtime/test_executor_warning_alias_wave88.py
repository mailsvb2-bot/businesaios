from __future__ import annotations

import runtime.executor as executor_module
from runtime.executor_runtime_support import emit_throttled_executor_warning


def test_runtime_executor_warning_alias_points_to_canonical_support_function() -> None:
    assert executor_module._throttled_exec_warn is emit_throttled_executor_warning
