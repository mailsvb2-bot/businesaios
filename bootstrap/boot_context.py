from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

"""BootPhase enum, BootContext typestate, BootConfigError.

Extracted from system_builder.py to eliminate god-module.
Public API is unchanged; system_builder.py re-exports everything.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Protocol


class BootConfigError(RuntimeError):
    """Raised when runtime boot config is invalid for the chosen environment."""


class BootPhase(IntEnum):
    """Strict boot phase ordering.

    Keep phases monotonic. New phases must be inserted with care.
    """

    P00_REGISTRIES = 0
    P10_STORAGE_PATHS = 10
    P15_PROD_GUARDS = 15
    P18_DIAGNOSTICS = 18
    P20_KEYRING = 20
    P30_STORES = 30
    P40_SETTINGS_FLAGS = 40
    P50_OUTBOUND = 50
    P60_RETENTION = 60
    P70_POLICIES = 70


@dataclass
class BootContext:
    """Minimal contract for phased boot.

    Prevents accidental reordering / using objects before init.
    """

    phase: BootPhase = BootPhase.P00_REGISTRIES
    history: list[BootPhase] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)

    def enter(self, phase: BootPhase) -> None:
        if self.history:
            if int(phase) <= int(self.history[-1]):
                raise BootConfigError(
                    f"Boot phase order violation: trying to enter {phase.name} after {self.history[-1].name}"
                )
        else:
            if phase != BootPhase.P00_REGISTRIES:
                raise BootConfigError(
                    f"Boot phase order violation: first phase must be {BootPhase.P00_REGISTRIES.name}"
                )
        self.phase = phase
        self.history.append(phase)

    def set_value(self, key: str, value: Any, *, min_phase: BootPhase | None = None) -> None:
        if min_phase is not None and int(self.phase) < int(min_phase):
            raise BootConfigError(
                f"BootContext.set_value('{key}') requires phase >= {min_phase.name}, current={self.phase.name}"
            )
        self.values[key] = value

    def require_value(self, key: str, *, min_phase: BootPhase | None = None) -> Any:
        if min_phase is not None and int(self.phase) < int(min_phase):
            raise BootConfigError(
                f"BootContext.require_value('{key}') requires phase >= {min_phase.name}, current={self.phase.name}"
            )
        if key not in self.values:
            raise BootConfigError(f"BootContext missing required value: {key}")
        return self.values[key]

    def get_value(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def self_check(self) -> None:
        """Short, cheap invariant check to catch future regressions."""
        expected_prefix = [
            BootPhase.P00_REGISTRIES,
            BootPhase.P10_STORAGE_PATHS,
            BootPhase.P15_PROD_GUARDS,
            BootPhase.P18_DIAGNOSTICS,
            BootPhase.P20_KEYRING,
            BootPhase.P30_STORES,
            BootPhase.P40_SETTINGS_FLAGS,
            BootPhase.P50_OUTBOUND,
            BootPhase.P60_RETENTION,
            BootPhase.P70_POLICIES,
        ]
        if self.history[: len(expected_prefix)] != expected_prefix:
            got = ",".join(p.name for p in self.history)
            exp = ",".join(p.name for p in expected_prefix)
            raise BootConfigError(f"Boot phases mismatch. expected_prefix=[{exp}] got=[{got}]")
        if "telegram_outbound_queue" not in self.values:
            raise BootConfigError(
                "Boot invariant violated: telegram_outbound_queue was not initialized (missing key)"
            )


from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BootRequest:
    """External request that enters the product-contract boot pipeline."""

    tenant_id: str
    user_id: str
    entrypoint: str
    hints: dict[str, str]

    def self_check(self) -> "BootRequest":
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.user_id or "").strip():
            raise ValueError("user_id is required")
        if not str(self.entrypoint or "").strip():
            raise ValueError("entrypoint is required")
        if not isinstance(self.hints, dict):
            raise ValueError("hints must be a dict")
        return self


@dataclass(frozen=True)
class SelectedProduct:
    """Phase output: product contract was selected and validated."""

    req: BootRequest
    contract: Any


@dataclass(frozen=True)
class AccessEnforced:
    """Phase output: product access decision was produced."""

    selected: SelectedProduct
    access: Any


@dataclass(frozen=True)
class ModulesWired:
    """Phase output: runtime services were wired for the selected product."""

    enforced: AccessEnforced
    services: dict[str, Any]


@dataclass(frozen=True)
class ReadySystem:
    """Final typed output of product-contract boot."""

    product_id: str
    domain: str
    access: Any
    services: dict[str, Any]


class ProductSelectorPort(Protocol):
    def select_product(self, req: BootRequest) -> SelectedProduct: ...


class AccessEnforcerPort(Protocol):
    def enforce_access(self, selected: SelectedProduct) -> AccessEnforced: ...


class ModuleWiringPort(Protocol):
    def wire_modules(self, enforced: AccessEnforced) -> ModulesWired: ...


class BootPipeline:
    """Small typed pipeline for product-contract boot.

    Keeping the pipeline here prevents `system_builder.py` from becoming a god-module
    while also giving import-lock tests a single stable contract.
    """

    def __init__(
        self,
        *,
        selector: ProductSelectorPort,
        enforcer: AccessEnforcerPort,
        wiring: ModuleWiringPort,
    ) -> None:
        self._selector = selector
        self._enforcer = enforcer
        self._wiring = wiring

    def boot(self, req: BootRequest) -> ReadySystem:
        selected = self._selector.select_product(req)
        enforced = self._enforcer.enforce_access(selected)
        wired = self._wiring.wire_modules(enforced)
        return ReadySystem(
            product_id=str(getattr(selected.contract, 'product_id', '')),
            domain=str(getattr(selected.contract, 'domain', '')),
            access=enforced.access,
            services=dict(wired.services),
        )
