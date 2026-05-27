from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from config.env_flags import env_str
from core.observability.silent import swallow


def _read_text_best_effort(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _resolve_build_meta() -> Dict[str, str]:
    """Best-effort build metadata.

    - build_id: env BUILD_ID or RELEASE_TAG file
    - version: env APP_VERSION or VERSION file
    """
    root = Path(__file__).resolve().parents[2]
    build_id = env_str("BUILD_ID", "").strip() or _read_text_best_effort(root / "RELEASE_TAG")
    version = env_str("APP_VERSION", "").strip() or _read_text_best_effort(root / "VERSION")
    out: Dict[str, str] = {}
    if build_id:
        out["build_id"] = build_id
    if version:
        out["version"] = version
    return out


def with_retention_telemetry(payload: Dict[str, Any], *, user_id: str) -> Dict[str, Any]:
    """Adds stable metadata fields for analytics.

    Safe-by-default: never raises, never mutates caller payload.
    """
    try:
        from core.retention.sandbox import retention_is_allowed, retention_sandbox_enabled

        sandbox_on = bool(retention_sandbox_enabled())
        allowed = bool(retention_is_allowed(user_id))
        sandbox = bool(sandbox_on and allowed)
    except Exception:
        sandbox = False

    out = dict(payload or {})
    meta = dict(out.get("meta") or {})
    meta.setdefault("retention", {})
    retention_meta = dict(meta.get("retention") or {})
    retention_meta.setdefault("sandbox", sandbox)

    # Build/version markers for retention analytics.
    try:
        build = _resolve_build_meta()
        for k, v in build.items():
            retention_meta.setdefault(k, v)
    except Exception:
        swallow(__name__, 'core/retention/telemetry.py')

    meta["retention"] = retention_meta
    out["meta"] = meta
    return out
