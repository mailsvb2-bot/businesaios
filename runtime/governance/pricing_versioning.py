"""Production pricing-version fingerprint gate."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_path, env_str

_PRICING_FIELDS = {"currency", "default_price_rub", "subscriber_price_rub", "price_rub", "trial_price_rub", "price_caps"}


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_pricing_fingerprint(pricing_config: Any) -> str:
    if hasattr(pricing_config, "__dict__"):
        data = dict(pricing_config.__dict__ or {})
    else:
        try:
            data = asdict(pricing_config)  # type: ignore[arg-type]
        except Exception:
            data = dict(pricing_config)  # type: ignore[arg-type]
    filtered = {key: data.get(key) for key in sorted(_PRICING_FIELDS) if key in data}
    return hashlib.sha256(_stable_json(filtered).encode("utf-8")).hexdigest()


def _looks_like_default_version(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return normalized in {"v1", "1", "0", "default", "dev", "test"} or normalized.startswith("v0")


def validate_explicit_pricing_version(value: str) -> str:
    pricing_version = str(value or "").strip()
    if not pricing_version:
        raise RuntimeError("PRODUCTION_STRICT_MODE=1 requires PRICING_VERSION to be set")
    if _looks_like_default_version(pricing_version):
        raise RuntimeError(f"PROD_STRICT_PRICING_VERSION_INVALID:{pricing_version}")
    return pricing_version


def get_pricing_version() -> str:
    """Resolve legacy override only for callers outside strict production."""
    version = env_str("PRICING_VERSION", "").strip()
    if version:
        return version
    override_path = str(env_path("PRICING_VERSION_OVERRIDE_PATH", "data/pricing_version_override.txt")).strip()
    if override_path:
        try:
            with open(override_path, encoding="utf-8") as handle:
                return handle.read().strip()
        except Exception:
            swallow(__name__, "runtime/governance/pricing_versioning.py")
    return ""


def _pricing_fingerprint_path() -> Path:
    explicit = env_str("PRICING_FINGERPRINT_PATH", "").strip()
    return Path(explicit) if explicit else env_path("DATA_DIR", "data") / "governance" / "pricing_fingerprint.json"


def _write_fingerprint(path: Path, *, pricing_version: str, fingerprint: str) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"pricing_version": pricing_version, "fingerprint": fingerprint}, handle, ensure_ascii=False, indent=2)


def enforce_pricing_versioning_or_raise(*, pricing_config: Any, production_strict: bool, log: Any) -> None:
    if not production_strict:
        return
    # Strict production reads the canonical environment directly. The optional
    # compatibility override in get_pricing_version() is never a second authority.
    pricing_version = validate_explicit_pricing_version(env_str("PRICING_VERSION", ""))
    path = _pricing_fingerprint_path()
    fingerprint = compute_pricing_fingerprint(pricing_config)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if path.exists():
        try:
            with path.open(encoding="utf-8") as handle:
                previous = json.load(handle)
        except Exception:
            previous = None
    if not isinstance(previous, dict) or not previous.get("fingerprint"):
        _write_fingerprint(path, pricing_version=pricing_version, fingerprint=fingerprint)
        log.info("[pricing] versioning initialized: PRICING_VERSION=%s fp=%s", pricing_version, fingerprint[:8])
        return
    previous_version = str(previous.get("pricing_version", "") or "").strip()
    previous_fingerprint = str(previous.get("fingerprint", "") or "").strip()
    if fingerprint != previous_fingerprint:
        if pricing_version == previous_version:
            raise RuntimeError(
                "Pricing changed but PRICING_VERSION did not change. "
                f"prev_version={previous_version} current_version={pricing_version}"
            )
        _write_fingerprint(path, pricing_version=pricing_version, fingerprint=fingerprint)
        log.warning(
            "[pricing] pricing changed; bumped version %s -> %s (fp %s..)",
            previous_version,
            pricing_version,
            fingerprint[:8],
        )
        return
    log.info("[pricing] pricing stable: PRICING_VERSION=%s fp=%s", pricing_version, fingerprint[:8])
