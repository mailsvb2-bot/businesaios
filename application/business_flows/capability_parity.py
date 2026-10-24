"""User-facing messenger / Yandex Direct capability projection (port of donor capability_parity).

Pure: callers pass connection statuses and runtime flags (env mapping, preflight result);
nothing here reads the process environment, probes providers or writes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

CANON_CAPABILITY_PARITY = True
PLATFORMS = ("telegram", "vk", "max")
_TRUE = frozenset({"1", "true", "yes", "on"})


class Availability(StrEnum):
    ACTIVE = "active"
    ATTENTION = "attention"
    CONFIGURING = "configuring"
    CONNECTABLE = "connectable"
    CONNECTED_UNAVAILABLE = "connected_unavailable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class MessengerCapability:
    platform: str
    availability: Availability
    connection_statuses: tuple[str, ...]
    runtime_enabled: bool
    runtime_ready: bool
    setup_available: bool

    @property
    def active(self) -> bool:
        return "active" in self.connection_statuses

    @property
    def can_connect(self) -> bool:
        return self.availability == Availability.CONNECTABLE and self.setup_available


@dataclass(frozen=True, slots=True)
class AdvertisingCapability:
    availability: Availability
    connection_statuses: tuple[str, ...]
    runtime_enabled: bool


@dataclass(frozen=True, slots=True)
class BusinessCapabilities:
    messengers: tuple[MessengerCapability, ...]
    yandex_direct: AdvertisingCapability | None

    def messenger(self, platform: str) -> MessengerCapability:
        p = str(getattr(platform, "value", platform) or "").strip().lower()
        return next(m for m in self.messengers if m.platform == p)


def _flag(env: Mapping[str, str], key: str) -> bool:
    return str(env.get(key) or "").strip().lower() in _TRUE


def omnichannel_enabled(env: Mapping[str, str]) -> bool:
    return _flag(env, "CLIENTPLATFORM_OMNICHANNEL_INGRESS_ENABLED")


def native_dispatch_enabled(env: Mapping[str, str]) -> bool:
    raw = str(env.get("CLIENTPLATFORM_DISPATCH_RUNTIME_ENABLED") or "").strip()
    return omnichannel_enabled(env) if not raw else raw.lower() in _TRUE


def native_runtime_state(env: Mapping[str, str], preflight: Callable[[], object]) -> tuple[bool, bool]:
    """(enabled, ready) for VK/MAX; a failing preflight means enabled-but-not-ready."""
    if not omnichannel_enabled(env) or not native_dispatch_enabled(env):
        return False, False
    try:
        pf = preflight()
    except (OSError, ValueError, TypeError, RuntimeError, AttributeError):
        return True, False
    enabled = bool(getattr(pf, "omnichannel_enabled", False))
    return enabled, bool(enabled and getattr(pf, "omnichannel_ready", False))


def setup_available(env: Mapping[str, str], public_base_url: str) -> bool:
    return bool(omnichannel_enabled(env) and str(public_base_url or "").strip().startswith("https://"))


def availability(*, statuses: tuple[str, ...], runtime_enabled: bool, runtime_ready: bool,
                 setup: bool) -> Availability:
    if "active" in statuses:
        if not runtime_enabled:
            return Availability.CONNECTED_UNAVAILABLE
        return Availability.ACTIVE if runtime_ready else Availability.ATTENTION
    if "attention" in statuses:
        return Availability.ATTENTION
    if "pending" in statuses:
        return Availability.CONFIGURING if runtime_enabled and runtime_ready else Availability.CONNECTED_UNAVAILABLE
    if runtime_enabled and runtime_ready and setup:
        return Availability.CONNECTABLE
    return Availability.UNAVAILABLE


def _norm(value: object) -> str:
    return str(getattr(value, "value", value)).strip().lower()


def project_messengers(connections: Iterable[object], *, setup: bool, enabled: Mapping[str, bool],
                       ready: Mapping[str, bool]) -> tuple[MessengerCapability, ...]:
    by: dict[str, list[str]] = {p: [] for p in PLATFORMS}
    for c in connections:
        plat, st = c if isinstance(c, tuple) and len(c) == 2 else (c.platform, c.status)  # type: ignore[attr-defined]
        if _norm(plat) in by:
            by[_norm(plat)].append(_norm(st))
    out = []
    for p in PLATFORMS:
        sts, en, rd = tuple(by[p]), bool(enabled.get(p, False)), bool(ready.get(p, False))
        out.append(MessengerCapability(p, availability(statuses=sts, runtime_enabled=en, runtime_ready=rd, setup=setup),
                                       sts, en, rd, setup))
    return tuple(out)


def project_yandex(statuses: tuple[str, ...] | None, *, runtime_enabled: bool) -> AdvertisingCapability | None:
    """``None`` statuses = actor may not see ad connections (permission denied)."""
    if statuses is None:
        return None
    sts = tuple(_norm(s) for s in statuses)
    if "active" in sts:
        av = Availability.ACTIVE if runtime_enabled else Availability.CONNECTED_UNAVAILABLE
    elif "attention" in sts:
        av = Availability.ATTENTION
    elif "pending" in sts:
        av = Availability.CONFIGURING
    else:
        av = Availability.CONNECTABLE if runtime_enabled else Availability.UNAVAILABLE
    return AdvertisingCapability(av, sts, runtime_enabled)


def business_capabilities(connections: Iterable[object], *, setup: bool, enabled: Mapping[str, bool],
                          ready: Mapping[str, bool], ad_statuses: tuple[str, ...] | None = (),
                          ad_runtime_enabled: bool = False, include_advertising: bool = True) -> BusinessCapabilities:
    return BusinessCapabilities(
        project_messengers(connections, setup=setup, enabled=enabled, ready=ready),
        project_yandex(ad_statuses, runtime_enabled=ad_runtime_enabled) if include_advertising else None,
    )


__all__ = [
    "CANON_CAPABILITY_PARITY", "AdvertisingCapability", "Availability", "BusinessCapabilities",
    "MessengerCapability", "availability", "business_capabilities", "native_runtime_state",
    "project_messengers", "project_yandex", "setup_available",
]
