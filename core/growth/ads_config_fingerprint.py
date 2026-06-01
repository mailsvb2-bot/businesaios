from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any


def ads_config_fingerprint(*, ads_entitlements: Any, daily_limits: Any) -> str:
    payload = {"ads_entitlements": _to_plain(ads_entitlements), "daily_limits": _to_plain(daily_limits)}
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def _to_plain(x: Any) -> Any:
    if x is None:
        return None
    if is_dataclass(x):
        return {k: _to_plain(v) for k,v in asdict(x).items()}
    if isinstance(x, dict):
        return {str(k): _to_plain(v) for k,v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_plain(v) for v in x]
    if hasattr(x, "value"):
        try:
            return x.value
        except Exception:
            return str(x)
    return x
