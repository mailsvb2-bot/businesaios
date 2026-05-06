from __future__ import annotations

"""Explicit compatibility wrapper with a real module file."""

CANON_COMPAT_SHIM = True

from config import MAX_ROUTING_CANDIDATES as MAX_ROUTING_CANDIDATES
from config import MAX_RUNNER_UPS as MAX_RUNNER_UPS
from config import ROUTING_SCORE_FLOOR as ROUTING_SCORE_FLOOR
from config import MAX_RETRY_ATTEMPTS as MAX_RETRY_ATTEMPTS
from config import MANUAL_REVIEW_REASON as MANUAL_REVIEW_REASON

__all__ = ['MAX_ROUTING_CANDIDATES', 'MAX_RUNNER_UPS', 'ROUTING_SCORE_FLOOR', 'MAX_RETRY_ATTEMPTS', 'MANUAL_REVIEW_REASON']
