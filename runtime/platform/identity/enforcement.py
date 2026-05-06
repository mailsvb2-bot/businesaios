from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Tuple

from runtime.platform.identity.entitlements import AccessController, AccessDecision


class ProductContractView(Protocol):
    """Minimal view needed for platform enforcement.

    Note: platform_layer must not import core.* (layering).
    """

    product_id: str


@dataclass(frozen=True)
class EnforcedProductAccess:
    """Output of enforcement, carried forward into runtime as immutable proof."""

    tenant_id: str
    user_id: str
    product_id: str
    allowed: bool
    reason: str
    missing_entitlements: Tuple[str, ...] = ()


class ProductAccessEnforcer:
    """Converts ProductContract into an enforced access decision.

    Contract currently carries a string entry_policy (engine pointer). We keep enforcement
    platform-owned by using env-driven minimal gates:
      - requires_auth: always True for interactive entrypoints (telegram/webapp)
      - required_entitlements: empty by default (future: can be added to ProductContract)

    This file is intentionally small and strictly tenant-scoped.
    """

    def __init__(self, *, controller: AccessController) -> None:
        self._controller = controller

    def enforce(self, *, tenant_id: str, user_id: str, contract: ProductContractView) -> EnforcedProductAccess:
        # Today we treat interactive entrypoints as authenticated.
        # Product-level entitlement keys will be added to ProductContract in a dedicated patch.
        decision: AccessDecision = self._controller.check_access(
            tenant_id=tenant_id,
            user_id=user_id,
            requires_auth=True,
            required_entitlements=(),
        )
        return EnforcedProductAccess(
            tenant_id=tenant_id,
            user_id=user_id,
            product_id=contract.product_id,
            allowed=decision.allowed,
            reason=decision.reason,
            missing_entitlements=decision.missing_entitlements,
        )
