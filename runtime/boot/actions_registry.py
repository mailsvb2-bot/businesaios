"""Canonical runtime action registry (single source of truth).

Purpose:
- eliminate "second brain" by forcing every runtime action to be explicitly registered
- attach minimal contract metadata (idempotency + limits + verification) per action
- keep the public registry surface thin by delegating declarative data to
  ``runtime.boot.actions_catalog``
- enable lock-tests to fail CI on drift / unregistered actions

This file is intentionally boring and explicit.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from runtime.boot.actions_catalog import (
    BUILTIN_HANDLER_ACTIONS,
    EFFECT_ONLY_ACTIONS,
    INLINE_ALLOWLIST_NAMES,
    SPEC_ROWS,
    build_inline_allowlist,
    build_specs_registry,
    execution_category_for_action,
    external_confirmation_mode_for_action,
    handler_actions_from,
)

CANON_BOOT_WIRING_ONLY = True


LimitKind = Literal["none", "general", "llm", "ads", "payments", "admin"]
ExecutionCategory = Literal["external_effect", "internal_bookkeeping", "advisory"]
ExternalConfirmationMode = Literal["required", "not_required"]


@dataclass(frozen=True)
class ActionLimitsV1:
    schema_version: int = 1
    kind: LimitKind = "general"
    per_tenant_per_min: int = 120
    per_user_per_min: int = 60


@dataclass(frozen=True)
class ActionSpecV1:
    schema_version: int = 1
    name: str = ""
    handler_ref: str = ""
    requires_idempotency_key: bool = True
    limits: ActionLimitsV1 = ActionLimitsV1()
    execution_category: ExecutionCategory = "internal_bookkeeping"
    external_confirmation_mode: ExternalConfirmationMode = "not_required"


def _spec(name: str, handler_ref: str, *, idem: bool, kind: LimitKind, pt: int, pu: int) -> ActionSpecV1:
    return ActionSpecV1(
        name=name,
        handler_ref=handler_ref,
        requires_idempotency_key=bool(idem),
        limits=ActionLimitsV1(kind=kind, per_tenant_per_min=int(pt), per_user_per_min=int(pu)),
        execution_category=execution_category_for_action(name),
        external_confirmation_mode=external_confirmation_mode_for_action(name),
    )


class _SpecsRegistry(dict[str, ActionSpecV1]):
    def __iter__(self) -> Iterator[ActionSpecV1]:
        return iter(self.values())


SPECS: _SpecsRegistry = build_specs_registry(
    rows=SPEC_ROWS,
    spec_factory=_spec,
    registry_type=_SpecsRegistry,
)

INLINE_ALLOWLIST: set[str] = build_inline_allowlist(names=INLINE_ALLOWLIST_NAMES)


def get_spec(action: str) -> ActionSpecV1:
    name = str(action)
    if name not in SPECS:
        raise KeyError(name)
    return SPECS[name]


def all_actions() -> set[str]:
    return set(SPECS.keys())


def handler_actions() -> set[str]:
    return handler_actions_from(all_actions())


__all__ = [
    "ActionLimitsV1",
    "ActionSpecV1",
    "BUILTIN_HANDLER_ACTIONS",
    "EFFECT_ONLY_ACTIONS",
    "ExecutionCategory",
    "ExternalConfirmationMode",
    "INLINE_ALLOWLIST",
    "LimitKind",
    "SPECS",
    "all_actions",
    "get_spec",
    "handler_actions",
]
