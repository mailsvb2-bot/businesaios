from __future__ import annotations

from runtime.messaging_policy.policy_request import PolicyRequest


def keep_enabled(channels: tuple[str, ...], req: PolicyRequest) -> tuple[str, ...]:
    allowed = set(req.preference.enabled)
    return tuple(ch for ch in channels if ch in allowed)


def keep_verified_if_required(channels: tuple[str, ...], req: PolicyRequest) -> tuple[str, ...]:
    if not req.verified_only:
        return channels
    verified = set(req.preference.verified)
    return tuple(ch for ch in channels if ch in verified)


def drop_blocked(channels: tuple[str, ...], req: PolicyRequest) -> tuple[str, ...]:
    return tuple(ch for ch in channels if not req.delivery_snapshot.is_blocked(ch))


def drop_failed(channels: tuple[str, ...], req: PolicyRequest) -> tuple[str, ...]:
    return tuple(ch for ch in channels if not req.delivery_snapshot.is_failed(ch))


def rotate_for_attempt_index(channels: tuple[str, ...], req: PolicyRequest) -> tuple[str, ...]:
    if not channels:
        return channels
    idx = int(req.attempt_index or 0)
    if idx <= 0:
        return channels
    if idx >= len(channels):
        return ()
    return channels[idx:]


def rotate_for_unanswered(channels: tuple[str, ...], req: PolicyRequest) -> tuple[str, ...]:
    current = req.unanswered_snapshot.current_channel
    threshold = int(req.unanswered_threshold_s or 0)
    seconds = int(req.unanswered_snapshot.seconds_since_last_user_reply or 0)

    if not channels or not current or threshold <= 0 or seconds < threshold:
        return channels

    if current not in channels:
        return channels

    if len(channels) == 1:
        return channels

    return tuple(ch for ch in channels if ch != current) + (current,)
