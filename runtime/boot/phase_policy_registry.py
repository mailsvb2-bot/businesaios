from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bootstrap.failure_policy import raise_or_log_boot_failure
from governance.persistence_codec import atomic_write_json, exclusive_file_lock, read_json_or_default
from runtime.platform.config.env_flags import env_csv, env_int, env_str

CANON_BOOT_WIRING_ONLY = True
POLICY_RUNTIME_STATE_FILENAME = "policy_runtime_state.json"


class _PolicyRuntimeStateFileStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @staticmethod
    def _generation(payload: object) -> int:
        if payload is None:
            return 0
        if not isinstance(payload, Mapping):
            raise ValueError("POLICY_RUNTIME_STATE_PAYLOAD_INVALID")
        generation = payload.get("rollout_generation")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            raise ValueError("POLICY_RUNTIME_STATE_GENERATION_INVALID")
        return generation

    def load(self) -> Mapping[str, Any] | None:
        with exclusive_file_lock(self.path):
            payload = read_json_or_default(self.path, default=None)
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise ValueError("POLICY_RUNTIME_STATE_PAYLOAD_INVALID")
        return dict(payload)

    def save(self, payload: Mapping[str, Any], *, expected_generation: int) -> None:
        with exclusive_file_lock(self.path):
            current = read_json_or_default(self.path, default=None)
            observed_generation = self._generation(current)
            if observed_generation != int(expected_generation):
                raise RuntimeError("POLICY_RUNTIME_STATE_GENERATION_CONFLICT")
            atomic_write_json(self.path, dict(payload))


def _policy_runtime_state_path(base: str | Path) -> Path:
    return Path(base) / "governance" / POLICY_RUNTIME_STATE_FILENAME


def build_policy_registry(
    *,
    settings: Any,
    pricing: Any,
    retention: Any,
    logging_mod: Any,
    base: str | Path,
):
    from core.ai.policy_registry import PolicyRegistry

    preg = PolicyRegistry(runtime_state_store=_PolicyRuntimeStateFileStore(_policy_runtime_state_path(base)))
    admin_ids = _resolve_admin_ids(settings=settings)
    _register_core_policies(
        preg=preg,
        pricing=pricing,
        retention=retention,
        settings=settings,
        admin_ids=admin_ids,
    )
    _activate_bootstrap_policy(preg=preg, settings=settings)
    preg.restore_persisted_runtime_state()
    _enforce_pricing_versioning(
        settings=settings,
        pricing=pricing,
        logging_mod=logging_mod,
    )
    return preg


def _resolve_admin_ids(*, settings: Any) -> tuple[str, ...]:
    def _parse_admin_ids(raw: str) -> tuple[str, ...]:
        return tuple(
            part.strip()
            for part in (raw or "").split(",")
            if part.strip()
        )

    admin_ids = _parse_admin_ids(
        str(getattr(settings.guard, "admin_user_ids", "") or "")
    )
    if admin_ids:
        return admin_ids
    raw_ids = ",".join(env_csv("ADMIN_USER_IDS")) or ",".join(
        env_csv("ADMIN_IDS")
    )
    return _parse_admin_ids(raw_ids)


def _register_core_policies(
    *,
    preg: Any,
    pricing: Any,
    retention: Any,
    settings: Any,
    admin_ids: tuple[str, ...],
) -> None:
    from core.policies.demand_route_policy import DemandRoutePolicyV1
    from core.policies.offer_outcome_emit_policy import OfferOutcomeEmitPolicyV1
    from core.policies.payments_policies import PaymentsReconcilePolicyV1
    from core.policies.payments_webhook_policy import (
        PaymentsWebhookReconcilePolicyV1,
    )
    from core.policies.telegram.ingress_policy import TelegramIngressPolicyV1
    from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3

    preg.register(
        UnifiedTelegramPolicyV3(
            pricing_rub=int(pricing.default_price_rub),
            admin_user_ids=admin_ids,
            bot_username=str(
                getattr(settings.telegram, "bot_username", "") or ""
            ),
            gift_ttl_sec=int(
                getattr(settings.gift, "ttl_sec", 7 * 24 * 3600)
            ),
            retention=retention,
        )
    )
    preg.register(DemandRoutePolicyV1())
    preg.register(TelegramIngressPolicyV1())
    preg.register(
        PaymentsReconcilePolicyV1(
            window_min=env_int(
                "PAYMENTS_RECONCILE_WINDOW_MIN",
                30,
                lo=1,
            )
        )
    )
    preg.register(PaymentsWebhookReconcilePolicyV1())
    preg.register(OfferOutcomeEmitPolicyV1())


def _activate_bootstrap_policy(*, preg: Any, settings: Any) -> None:
    active_pid = (
        env_str("BOOT_ACTIVE_POLICY_ID", "").strip()
        or "telegram_policy@v3"
    )
    try:
        preg.activate_bootstrap(policy_id=active_pid)
    except Exception as exc:
        raise_or_log_boot_failure(
            component="bootstrap_policy_activation",
            exc=exc,
            settings=settings,
        )


def _enforce_pricing_versioning(
    *,
    settings: Any,
    pricing: Any,
    logging_mod: Any,
) -> None:
    from runtime.governance.pricing_versioning import (
        enforce_pricing_versioning_or_raise,
    )

    enforce_pricing_versioning_or_raise(
        pricing_config=pricing,
        production_strict=(
            settings.core.env == "prod"
            and settings.core.production_strict_mode
        ),
        log=logging_mod.getLogger("runtime.pricing"),
    )
