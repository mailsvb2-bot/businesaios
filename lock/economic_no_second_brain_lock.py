from __future__ import annotations

CANON_ECONOMIC_NO_SECOND_BRAIN_LOCK = True

FORBIDDEN_MARKERS = (
    'manual revenue recompute',
    'duplicate reconciliation logic',
    'custom billing math outside billing',
)


def validate_code(code: str) -> None:
    for marker in FORBIDDEN_MARKERS:
        if marker in code:
            raise RuntimeError('Second brain detected in economic layer')
