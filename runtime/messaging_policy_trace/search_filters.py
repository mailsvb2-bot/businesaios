from __future__ import annotations

from runtime.messaging_policy_trace.iso_time import safe_parse_iso_to_epoch_ms


def within_date_window(*, timestamp_ms: int = 0, created_at: str = '', date_from: str, date_to: str) -> bool:
    current = int(timestamp_ms or 0)
    if current <= 0 and str(created_at or '').strip():
        current = safe_parse_iso_to_epoch_ms(created_at)
    if current <= 0:
        return not date_from and not date_to
    if str(date_from or '').strip() and current < safe_parse_iso_to_epoch_ms(str(date_from)):
        return False
    if str(date_to or '').strip() and current > safe_parse_iso_to_epoch_ms(str(date_to)):
        return False
    return True


def user_matches(*, expected_user_id: str, actual_user_id: str) -> bool:
    expected = str(expected_user_id or '').strip()
    if not expected:
        return True
    return str(actual_user_id or '') == expected
