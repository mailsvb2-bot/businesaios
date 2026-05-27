"""Payment-specific effects protocol mixin.

Extracted from EffectsPort (Patch 05).
"""

from __future__ import annotations

from typing import Any, Protocol


class EffectsPaymentMixin(Protocol):
    """Payment side-effect methods."""

    def create_payment(self, **kw: Any) -> Any: ...
    def refund_payment(self, **kw: Any) -> Any: ...
    def reconcile_payment(self, **kw: Any) -> Any: ...
    def grant_access(self, **kw: Any) -> Any: ...
    def revoke_access(self, **kw: Any) -> Any: ...
