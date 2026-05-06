from __future__ import annotations

from typing import Any


def enforce_rate_limit(*, rate_limiter: Any, spec: Any, tenant_id: str, user_id: str) -> None:
    rate_limiter.assert_allowed(spec=spec, tenant_id=tenant_id, user_id=user_id, cost=1)
