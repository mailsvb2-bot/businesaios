"""Public facade for sealed economic execution-contract builders."""

from __future__ import annotations

import importlib
from typing import Any, Mapping

from runtime.firewall.import_guard import allow_internal_import

CANON_RUNTIME_ECONOMIC_EXECUTION_PUBLIC_SURFACE = True


def _owner():
    with allow_internal_import():
        return importlib.import_module(
            "runtime._internal" + ".economic_execution_contract"
        )


def build_click_provider_dispatch_execution_contract(
    provider_dispatch: Mapping[str, Any] | None,
):
    return _owner().build_click_provider_dispatch_execution_contract(provider_dispatch)


def build_spend_runtime_execution_contract(
    runtime_request: Mapping[str, Any] | None,
):
    return _owner().build_spend_runtime_execution_contract(runtime_request)


__all__ = [
    "CANON_RUNTIME_ECONOMIC_EXECUTION_PUBLIC_SURFACE",
    "build_click_provider_dispatch_execution_contract",
    "build_spend_runtime_execution_contract",
]
