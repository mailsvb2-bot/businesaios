from __future__ import annotations

from typing import Final


CANON_CLIENT_OUTCOME_AMENDMENT_POLICY = True

AMENDMENT_ALLOWED_STATUSES: Final[frozenset[str]] = frozenset({
    '',
    'executed',
    'verified',
    'verification_rejected',
})


def can_amend_for_commercial_status(commercial_status: object) -> bool:
    return str(commercial_status or '').strip() in AMENDMENT_ALLOWED_STATUSES
