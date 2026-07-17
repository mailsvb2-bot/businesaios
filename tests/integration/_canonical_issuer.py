from __future__ import annotations

from typing import TypeVar

from core.ai import set_decision_core_singleton

T = TypeVar("T")


def register_issue_owner(owner: T) -> T:
    """Register one test issuer through the production singleton boundary."""

    issue = getattr(owner, "issue", None)
    if not callable(issue):
        raise TypeError("integration decision issuer must provide issue(state)")
    set_decision_core_singleton(owner)
    return owner


__all__ = ["register_issue_owner"]
