from __future__ import annotations

CANON_ECONOMIC_TRUTH_LOCK = True

FORBIDDEN_PATTERNS = (
    'direct revenue calculation outside client_outcome',
    'manual reversal logic',
    'custom refund math outside corrected_economics',
)


def validate_no_economic_truth_bypass(module_code: str) -> None:
    normalized = str(module_code or '')
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in normalized:
            raise RuntimeError('Economic truth bypass detected')
