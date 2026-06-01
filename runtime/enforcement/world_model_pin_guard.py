from __future__ import annotations

from typing import Any

from runtime.enforcement import WorldModelPin, WorldModelPinCheckResult
from runtime.platform.config.env_flags import env_bool
from runtime.world_model import extract_world_model_metadata


class WorldModelPinMismatchError(RuntimeError):
    pass


def is_strict_world_model_pinning_enabled() -> bool:
    return env_bool("STRICT_WORLD_MODEL_PINNING", False)


def check_world_model_pin(
    *,
    pinned_meta: dict[str, Any] | None,
    state: Any,
) -> WorldModelPinCheckResult:
    pinned = WorldModelPin.from_payload(pinned_meta)
    current = extract_world_model_metadata(state=state)

    pinned_dict = pinned.to_dict()
    strict = is_strict_world_model_pinning_enabled()

    pinned_hash = pinned.pricing_world_model_hash
    current_hash = _as_str_or_none(current.get("pricing_world_model_hash"))

    if pinned_hash is None:
        return WorldModelPinCheckResult(
            ok=True,
            strict=strict,
            reason="no_pinned_pricing_world_model_hash",
            pinned=pinned_dict,
            current=current,
        )

    if current_hash is None:
        return WorldModelPinCheckResult(
            ok=not strict,
            strict=strict,
            reason="current_pricing_world_model_hash_missing",
            pinned=pinned_dict,
            current=current,
        )

    if pinned_hash != current_hash:
        return WorldModelPinCheckResult(
            ok=not strict,
            strict=strict,
            reason="pricing_world_model_hash_mismatch",
            pinned=pinned_dict,
            current=current,
        )

    return WorldModelPinCheckResult(
        ok=True,
        strict=strict,
        reason="world_model_pin_match",
        pinned=pinned_dict,
        current=current,
    )


def enforce_world_model_pin_or_raise(
    *,
    pinned_meta: dict[str, Any] | None,
    state: Any,
) -> WorldModelPinCheckResult:
    result = check_world_model_pin(
        pinned_meta=pinned_meta,
        state=state,
    )
    if not result.ok and result.strict:
        raise WorldModelPinMismatchError(result.reason)
    return result


def _as_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None
