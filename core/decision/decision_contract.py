from __future__ import annotations

"""Thin compatibility shim for ``application.decision.decision_contract``."""

from core.decision._compat import install_compat_module

install_compat_module(
    globals_dict=globals(),
    canonical_owner_module="application.decision.decision_contract",
)
