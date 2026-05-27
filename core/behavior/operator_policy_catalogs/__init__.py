"""Operator Policy Catalogs.

Policy catalogs constrain which behavior operators may be applied in a given
funnel stage and/or B2B actor role.

This is the 'safety rail' layer above Operator Catalogs (which only scale
operator parameters).

Rules:
- Policies may only allow/deny operator keys from the canonical operator set.
- Policies may *not* introduce new operator keys.
- When a policy denies an operator, the operator becomes a deterministic no-op.
"""
from __future__ import annotations

from .loader import load_operator_policy_catalog
from .model import OperatorPolicyCatalog, OperatorPolicyContext, OperatorPolicyRule
from .resolver import OperatorPolicyCatalogResolver

__all__ = [
    "OperatorPolicyCatalog",
    "OperatorPolicyContext",
    "OperatorPolicyRule",
    "OperatorPolicyCatalogResolver",
    "load_operator_policy_catalog",
]
