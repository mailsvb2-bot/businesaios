from __future__ import annotations

"""Pricing versioning gate for production strict.

Goal:
- Prevent silent price changes in production without an explicit version bump.

How it works:
- Compute fingerprint (sha256) from pricing-relevant fields.
- Persist last known {pricing_version, fingerprint} to a local json file.
- In strict prod:
    - PRICING_VERSION must be set and must not look like a default placeholder.
    - If fingerprint changes, PRICING_VERSION must change.

No side-effects on import.
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_path, env_str


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_pricing_fingerprint(pricing_config: Any) -> str:
    if hasattr(pricing_config, "__dict__"):
        data = dict(getattr(pricing_config, "__dict__") or {})
    else:
        try:
            data = asdict(pricing_config)  # type: ignore[arg-type]
        except Exception:
            data = dict(pricing_config)  # type: ignore[arg-type]

    allow = {
        "currency",
        "default_price_rub",
        "subscriber_price_rub",
        "price_rub",
        "trial_price_rub",
        "price_caps",
    }
    filtered: Dict[str, Any] = {k: data.get(k) for k in sorted(allow) if k in data}
    payload = _stable_json(filtered).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _looks_like_default_version(v: str) -> bool:
    vv = (v or "").strip().lower()
    return vv in {"v1", "1", "0", "default", "dev", "test"} or vv.startswith("v0")


def get_pricing_version() -> str:
    """Resolve PRICING_VERSION from env or an operator-controlled override file."""
    v = env_str("PRICING_VERSION", "").strip()
    if v:
        return v
    # Optional: allow a persisted override written by governed admin actions.
    override_path = str(env_path("PRICING_VERSION_OVERRIDE_PATH", "data/pricing_version_override.txt")).strip()
    if override_path:
        try:
            txt = open(override_path, encoding="utf-8").read().strip()
            if txt:
                return txt
        except Exception:
            swallow(__name__, 'runtime/governance/pricing_versioning.py')
    return ""


def enforce_pricing_versioning_or_raise(*, pricing_config: Any, production_strict: bool, log: Any) -> None:
    if not production_strict:
        return

    pricing_version = get_pricing_version()
    if not pricing_version:
        raise RuntimeError("PRODUCTION_STRICT_MODE=1 requires PRICING_VERSION to be set")
    if _looks_like_default_version(pricing_version):
        raise RuntimeError(f"PROD_STRICT_PRICING_VERSION_INVALID:{pricing_version}")

    path = str(env_path("PRICING_FINGERPRINT_PATH", "data/pricing_fingerprint.json")).strip()
    fp = compute_pricing_fingerprint(pricing_config)

    Path(path).parent.mkdir(parents=True, exist_ok=True)

    prev = None
    if Path(path).exists():
        try:
            with open(path, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = None

    if not isinstance(prev, dict) or not prev.get("fingerprint"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"pricing_version": pricing_version, "fingerprint": fp}, f, ensure_ascii=False, indent=2)
        log.info("[pricing] versioning initialized: PRICING_VERSION=%s fp=%s", pricing_version, fp[:8])
        return

    prev_v = str(prev.get("pricing_version", "") or "").strip()
    prev_fp = str(prev.get("fingerprint", "") or "").strip()

    if fp != prev_fp:
        if pricing_version == prev_v:
            raise RuntimeError(
                "Pricing changed but PRICING_VERSION did not change. "
                f"prev_version={prev_v} current_version={pricing_version}"
            )
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"pricing_version": pricing_version, "fingerprint": fp}, f, ensure_ascii=False, indent=2)
        log.warning("[pricing] pricing changed; bumped version %s -> %s (fp %s..)", prev_v, pricing_version, fp[:8])
        return

    log.info("[pricing] pricing stable: PRICING_VERSION=%s fp=%s", pricing_version, fp[:8])
