from __future__ import annotations

from typing import Any, Dict


def unwrap_call_result(*, method: str, done: Any, box: Dict[str, Any], timeout_s: float) -> Any:
    if not done.wait(timeout=float(timeout_s)):
        raise TimeoutError(f"TELEGRAM_OUTBOUND_TIMEOUT:{method}")
    if box.get("error") is not None:
        raise RuntimeError(str(box.get("error")))
    return box.get("result")


__all__ = ["unwrap_call_result"]
