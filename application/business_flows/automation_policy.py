"""Owner automation policy: versioned draft -> approve -> effective -> revoke, plus a fail-closed check.

Port of clientplatform ``automation_policy`` (+ domain ``evaluate_automation_policy``), reduced to
what the Telegram owner flow uses. Facts live in ``business_admin@v1`` next to approvals; a
check that needs approval produces the existing ``approval_requested`` fact. Nothing executes here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from application.business_flows import admin as ad
from application.business_flows.projection import stable_id

DAY_MS = 86_400_000
MONEY_ACTIONS = frozenset({"ads", "discount", "refund", "payment"})


@dataclass(frozen=True)
class Spec:
    allowed: tuple[str, ...]
    forbidden: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    max_minor: dict[str, int] = field(default_factory=dict)
    approval_required: tuple[str, ...] = ()
    days: int = 30


@dataclass
class Policy:
    version: int
    spec: Spec
    created_ms: int
    status: str = "draft"
    approved_ms: int = 0

    def effective(self, now_ms: int) -> bool:
        return self.status == "approved" and now_ms <= self.approved_ms + self.spec.days * DAY_MS


def _csv(v: str) -> tuple[str, ...]:
    return tuple(sorted({x.strip().casefold() for x in v.split(",") if x.strip()}))


def parse_spec(arg: str) -> Spec:
    """``allow=post,remind | deny=ads | channels=telegram | max=ads:5000 | approve=ads | days=30``."""
    kv: dict[str, str] = {}
    for part in str(arg or "").split("|"):
        k, sep, v = part.partition("=")
        if sep:
            kv[k.strip().casefold()] = v.strip()
    allowed = _csv(kv.get("allow", ""))
    if not allowed:
        raise ValueError("нужно allow=действия")
    max_minor: dict[str, int] = {}
    for item in _csv(kv.get("max", "")):
        act, _, rub = item.partition(":")
        max_minor[act] = ad.parse_money(rub)[0]
    days = int(kv.get("days", "30"))
    if not 1 <= days <= 365:
        raise ValueError("days 1..365")
    deny = _csv(kv.get("deny", ""))
    if set(allowed) & set(deny):
        raise ValueError("действие одновременно разрешено и запрещено")
    return Spec(allowed, deny, _csv(kv.get("channels", "")), max_minor, _csv(kv.get("approve", "")), days)


def replay(payloads: list[dict[str, Any]]) -> list[Policy]:
    out: list[Policy] = []
    for p in payloads:
        step = p.get("step")
        if step == "policy_drafted" and int(p["version"]) == len(out) + 1:
            s = p["spec"]
            spec = Spec(
                tuple(s["allowed"]),
                tuple(s["forbidden"]),
                tuple(s["channels"]),
                dict(s["max_minor"]),
                tuple(s["approval_required"]),
                int(s["days"]),
            )
            out.append(Policy(int(p["version"]), spec, int(p["at_ms"])))
        elif step == "policy_approved" and 0 < int(p["version"]) <= len(out):
            for o in out:
                if o.status == "approved":
                    o.status = "superseded"
            pol = out[int(p["version"]) - 1]
            pol.status, pol.approved_ms = "approved", int(p["at_ms"])
        elif step == "policy_revoked" and 0 < int(p["version"]) <= len(out):
            out[int(p["version"]) - 1].status = "revoked"
    return out


def draft(policies: list[Policy], arg: str, *, now_ms: int) -> dict[str, Any]:
    s = parse_spec(arg)
    spec = {
        "allowed": list(s.allowed),
        "forbidden": list(s.forbidden),
        "channels": list(s.channels),
        "max_minor": s.max_minor,
        "approval_required": list(s.approval_required),
        "days": s.days,
    }
    return {"step": "policy_drafted", "version": len(policies) + 1, "spec": spec, "at_ms": now_ms}


def latest(policies: list[Policy]) -> Policy | None:
    return policies[-1] if policies else None


def effective(policies: list[Policy], *, now_ms: int) -> Policy | None:
    return next((p for p in reversed(policies) if p.effective(now_ms)), None)


def approve(policies: list[Policy], *, now_ms: int) -> dict[str, Any]:
    p = latest(policies)
    if p is None or p.status != "draft":
        raise ValueError("нет черновика политики")
    return {"step": "policy_approved", "version": p.version, "at_ms": now_ms}


def revoke(policies: list[Policy], *, now_ms: int) -> dict[str, Any]:
    p = effective(policies, now_ms=now_ms)
    if p is None:
        raise ValueError("нет действующей политики")
    return {"step": "policy_revoked", "version": p.version, "at_ms": now_ms}


def check(
    policies: list[Policy], action: str, *, channel: str = "", amount_minor: int = 0, now_ms: int
) -> tuple[str, list[str]]:
    """-> ("allow" | "needs_approval" | "deny", reasons). Fail-closed: no policy => deny."""
    p = effective(policies, now_ms=now_ms)
    action, channel = action.casefold(), channel.casefold()
    if p is None:
        return "deny", ["нет действующей политики"]
    s, deny, need = p.spec, [], []
    if action in s.forbidden:
        deny.append("действие запрещено")
    if action not in s.allowed:
        deny.append("действие не разрешено")
    if s.channels and channel not in s.channels:
        deny.append(f"канал {channel or '—'} не разрешён")
    if action in MONEY_ACTIONS or amount_minor:
        cap = s.max_minor.get(action)
        if cap is None:
            deny.append("для денежного действия нет лимита")
        elif amount_minor > cap:
            deny.append(f"сумма выше лимита {ad.money(cap, 'RUB')}")
        need.append("денежное действие")
    if action in s.approval_required:
        need.append("требует подтверждения по политике")
    if deny:
        return "deny", deny
    return ("needs_approval", need) if need else ("allow", ["в рамках политики"])


def approval_for(action: str, channel: str, amount_minor: int, *, version: int, now_ms: int) -> dict[str, Any]:
    ref = stable_id("polchk", str(version), action, channel, str(amount_minor), str(now_ms // DAY_MS))
    return ad.request_approval(f"Автоматизация: {action} ({channel or '—'})", amount_minor, "RUB", source_ref=ref)


def render(policies: list[Policy], *, now_ms: int) -> str:
    p, eff = latest(policies), effective(policies, now_ms=now_ms)
    if p is None:
        return "📜 Политики автоматизации нет. /policy_draft allow=post,remind | max=ads:5000 | approve=ads | days=30"

    def fmt(x: Policy) -> str:
        s = x.spec
        lim = ", ".join(f"{k}≤{ad.money(v, 'RUB')}" for k, v in sorted(s.max_minor.items())) or "—"
        return (
            f"v{x.version} ({x.status}): разрешено {', '.join(s.allowed)}; запрещено {', '.join(s.forbidden) or '—'}; "
            f"каналы {', '.join(s.channels) or 'любые'}; лимиты {lim}; подтверждение {', '.join(s.approval_required) or '—'}; {s.days} дн."
        )

    head = "📜 Политика автоматизации\n" + (
        f"Действует: {fmt(eff)}" if eff else "Действующей политики нет — всё запрещено."
    )
    return head + (f"\nПоследняя версия: {fmt(p)}" if p is not eff else "")
