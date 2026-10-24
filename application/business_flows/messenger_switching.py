"""Staff messenger switch + public customer deep links (port of donor messenger_switching).

Pure over recorded facts: Telegram targets come from completed ``bot_provisioning`` requests
(username only, never the credential), VK from active ``vk_community`` connection rows. A target
is used only when it is unambiguous. Actor/tenant resolution belongs to the route + DecisionCore.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

CANON_MESSENGER_SWITCHING = True
PLATFORMS = ("telegram", "vk", "max")
_COMMAND_RE = re.compile(r"cpm:switch:(telegram|vk|max):([1-9][0-9]{0,18})")
_TG = re.compile(r"[A-Za-z0-9_]{5,32}")
_MAX = re.compile(r"[A-Za-z0-9_.-]{1,80}")
_START = re.compile(r"[A-Za-z0-9_-]{1,128}")


class MessengerSwitchRejected(RuntimeError):
    """A staff messenger switch target is unavailable or ambiguous."""


@dataclass(frozen=True)
class StaffDestination:
    user_id: int
    platform: str
    public_target: str


@dataclass(frozen=True)
class PublicDestination:
    platform: str
    url: str


def _one(values: Iterable[str]) -> str | None:
    vs = sorted({v.strip() for v in values if v and v.strip()})
    return vs[0] if len(vs) == 1 else None


def public_target(platform: str, *, bots: Iterable[Any], connections: Iterable[Mapping[str, Any]]) -> str | None:
    if platform == "vk":
        v = _one(str(c.get("external_account_id") or "") for c in connections
                 if c.get("platform") == "vk" and c.get("status") == "active"
                 and c.get("connection_type") == "vk_community")
        return v if v and v.isdigit() and int(v) > 0 else None
    if platform == "telegram":
        v = _one(str(b.username) for b in bots if str(getattr(b.status, "value", b.status)) == "completed")
        return v if v and _TG.fullmatch(v) else None
    if platform == "max":
        v = _one(str(c.get("external_account_id") or "") for c in connections
                 if c.get("platform") == "max" and c.get("status") == "active")
        return v if v and _MAX.fullmatch(v) else None
    return None


def public_destination(platform: str, start_payload: str, **src: Any) -> PublicDestination | None:
    payload = str(start_payload or "").strip()
    if _START.fullmatch(payload) is None:
        raise ValueError("messenger start payload is invalid")
    if platform not in PLATFORMS:
        raise ValueError("unsupported messenger destination platform")
    target = public_target(platform, **src)
    if target is None:
        return None
    if platform == "vk":
        return PublicDestination(platform, f"https://vk.com/write-{target}?ref={payload}")
    host = "t.me" if platform == "telegram" else "max.ru"
    return PublicDestination(platform, f"https://{host}/{target}?start={payload}")  # payload is URL-safe


def public_destinations(start_payload: str, **src: Any) -> tuple[PublicDestination, ...]:
    return tuple(d for p in PLATFORMS if (d := public_destination(p, start_payload, **src)) is not None)


def available_switches(**src: Any) -> tuple[str, ...]:
    return tuple(p for p in PLATFORMS if public_target(p, **src))


def switch_command(user_id: int, platform: str) -> str:
    p = str(platform or "").strip().lower()
    if p not in PLATFORMS or int(user_id) <= 0:
        raise ValueError("invalid messenger switch")
    return f"cpm:switch:{p}:{int(user_id)}"


def parse_switch_command(command: str) -> tuple[str, int] | None:
    m = _COMMAND_RE.fullmatch(str(command or "").strip())
    return None if m is None else (m.group(1), int(m.group(2)))


def switch_destination(command: str, **src: Any) -> StaffDestination | None:
    parsed = parse_switch_command(command)
    if parsed is None:
        return None
    target = public_target(parsed[0], **src)
    if target is None:
        raise MessengerSwitchRejected("messenger switch target is unavailable or ambiguous")
    return StaffDestination(parsed[1], parsed[0], target)


__all__ = ["CANON_MESSENGER_SWITCHING", "MessengerSwitchRejected", "PublicDestination", "StaffDestination",
           "available_switches", "parse_switch_command", "public_destination", "public_destinations",
           "public_target", "switch_command", "switch_destination"]
