from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from config import FRAUD_RISK_CEILING as FRAUD_RISK_CEILING
from config import NO_RESPONSE_RATE_CEILING as NO_RESPONSE_RATE_CEILING
from config import QUALITY_FLOOR as QUALITY_FLOOR
from config import REPUTATION_FLOOR as REPUTATION_FLOOR

__all__ = ['QUALITY_FLOOR', 'REPUTATION_FLOOR', 'NO_RESPONSE_RATE_CEILING', 'FRAUD_RISK_CEILING']
