"""Pricing governance I/O and validation. Executed ONLY via RuntimeExecutor."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime._internal.effects_domains.admin_pricing_support import persist_pricing_version_override
from runtime.platform.config.env_flags import env_bool, env_path


def validate_pricing_change(
    *,
    admin_id: str,
    requested_by: str | None,
    pricing_version: str,
) -> None:
    """Raise RuntimeError if governance validation fails."""

    requested = str(requested_by or "").strip()
    if requested and requested == str(admin_id):
        allow = env_bool("ALLOW_SELF_APPROVE", False)
        if not allow:
            raise RuntimeError("SELF_APPROVAL_FORBIDDEN")

    version = str(pricing_version or "").strip()
    if not version:
        raise RuntimeError("PRICING_VERSION_REQUIRED")

    if env_bool("PRODUCTION_STRICT_MODE", False):
        lowered = version.lower().strip()
        if lowered in {"v1", "1", "default"} or lowered.startswith("v1."):
            raise RuntimeError("PRICING_VERSION_LOOKS_DEFAULT")


def _restore_file(*, path: Path, existed: bool, content: bytes) -> None:
    if not existed:
        path.unlink(missing_ok=True)
        return
    restore_tmp = path.with_suffix(path.suffix + ".rollback.tmp")
    restore_tmp.write_bytes(content)
    restore_tmp.replace(path)


@dataclass
class PricingChangeTransaction:
    plans_path: Path
    override_path: Path
    plans_tmp: Path
    override_tmp: Path
    original_plans: bytes
    original_override: bytes
    override_existed: bool
    result: dict[str, Any]
    applied: bool = False
    finalized: bool = False

    def apply(self) -> dict[str, Any]:
        if self.finalized:
            raise RuntimeError("PRICING_TRANSACTION_FINALIZED")
        if self.applied:
            return dict(self.result)
        try:
            self.plans_tmp.replace(self.plans_path)
            self.override_tmp.replace(self.override_path)
        except Exception as exc:
            try:
                self.rollback()
            except Exception as rollback_exc:
                raise RuntimeError(
                    f"PRICING_ROLLBACK_FAILED:{rollback_exc.__class__.__name__}:{rollback_exc}"
                ) from exc
            raise RuntimeError(f"PRICING_COMMIT_FAILED:{exc.__class__.__name__}:{exc}") from exc
        self.applied = True
        return dict(self.result)

    def rollback(self) -> None:
        if self.finalized:
            raise RuntimeError("PRICING_TRANSACTION_FINALIZED")
        _restore_file(
            path=self.plans_path,
            existed=True,
            content=self.original_plans,
        )
        _restore_file(
            path=self.override_path,
            existed=bool(self.override_existed),
            content=self.original_override,
        )
        self.applied = False
        self._cleanup_temps()

    def finalize(self) -> None:
        self._cleanup_temps()
        self.finalized = True

    def _cleanup_temps(self) -> None:
        self.plans_tmp.unlink(missing_ok=True)
        self.override_tmp.unlink(missing_ok=True)


def prepare_plan_price_update(
    *,
    plan_id: int,
    new_price: int,
    pricing_version: str,
    plans_path: Path | None = None,
    override_path: Path | None = None,
) -> PricingChangeTransaction:
    """Prepare both pricing files before any active state is replaced."""

    plan = int(plan_id)
    price = int(new_price)
    version = str(pricing_version or "").strip()
    if not version:
        raise RuntimeError("PRICING_VERSION_REQUIRED")

    path = plans_path or env_path("PLANS_PATH", "data/plans.json")
    override = override_path or env_path(
        "PRICING_VERSION_OVERRIDE_PATH",
        "data/pricing_version_override.txt",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    override.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        raise RuntimeError(f"PLANS_NOT_FOUND:{path}")

    original_plans = path.read_bytes()
    override_existed = override.exists()
    original_override = override.read_bytes() if override_existed else b""

    try:
        data = json.loads(original_plans.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"PLANS_READ_FAILED:{exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError("PLANS_FORMAT_INVALID")

    updated = False
    for item in data:
        if not isinstance(item, dict):
            continue
        if int(item.get("plan_id") or -1) == plan:
            item["price"] = price
            updated = True
            break
    if not updated:
        raise RuntimeError(f"PLAN_ID_NOT_FOUND:{plan}")

    plans_tmp = path.with_suffix(path.suffix + ".pricing.tmp")
    override_tmp = override.with_suffix(override.suffix + ".pricing.tmp")
    plans_tmp.unlink(missing_ok=True)
    override_tmp.unlink(missing_ok=True)

    try:
        plans_tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        persist_pricing_version_override(
            override_path=override_tmp,
            pricing_version=version,
        )
    except Exception as exc:
        plans_tmp.unlink(missing_ok=True)
        override_tmp.unlink(missing_ok=True)
        raise RuntimeError(f"PRICING_PREPARE_FAILED:{exc.__class__.__name__}:{exc}") from exc

    return PricingChangeTransaction(
        plans_path=path,
        override_path=override,
        plans_tmp=plans_tmp,
        override_tmp=override_tmp,
        original_plans=original_plans,
        original_override=original_override,
        override_existed=override_existed,
        result={
            "plan_id": plan,
            "new_price": price,
            "pricing_version": version,
            "plans_path": str(path),
            "override_path": str(override),
            "override_persisted": True,
        },
    )


def execute_plan_price_update(
    *,
    plan_id: int,
    new_price: int,
    pricing_version: str,
    plans_path: Path | None = None,
    override_path: Path | None = None,
) -> dict[str, Any]:
    """Compatibility entrypoint for an immediate rollback-consistent commit."""

    transaction = prepare_plan_price_update(
        plan_id=int(plan_id),
        new_price=int(new_price),
        pricing_version=str(pricing_version),
        plans_path=plans_path,
        override_path=override_path,
    )
    try:
        return transaction.apply()
    finally:
        transaction.finalize()


__all__ = [
    "PricingChangeTransaction",
    "execute_plan_price_update",
    "prepare_plan_price_update",
    "validate_pricing_change",
]
