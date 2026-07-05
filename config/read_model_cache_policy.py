from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class ReadModelCachePolicy:
    default_window_s: float = 5.0
    min_window_s: float = 0.0
    max_window_s: float = 60.0
    default_empty_watermark_ms: int = 0


DEFAULT_READ_MODEL_CACHE_POLICY = ReadModelCachePolicy()
