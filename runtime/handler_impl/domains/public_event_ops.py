"""Public (online) events in the bot: create/publish, register, CRM projection, reminder links.

Ops of event_series@v1. Facts are stored as event_series@v1 tracked payloads (public_events steps are
``pub_*`` / ``channel_*`` and ignored by event_series.replay). CRM writes go only through the executor
effect ``ensure_customer_identity``; reminder links are issued only for CRM-projected registrations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

PUB_OPS = frozenset({"pub_create", "pub_register", "pub_links", "pub_verify"})


class _ExecutorCrm:
    """crm.CustomerRegistry-shaped adapter over the executor effect (no direct registry access here)."""

    def __init__(self, effects: Any, env: Any) -> None:
        self._fx, self._env = effects, env

    def _call(self, **kw: Any) -> dict[str, Any]:
        return self._fx.ensure_customer_identity(decision_id=str(self._env.decision.decision_id),
                                                 correlation_id=str(self._env.decision.correlation_id), **kw)

    def ensure_customer_identity(self, **kw: Any) -> Any:
        r = self._call(**kw)
        if not r.get("ok"):
            raise LookupError(str(r.get("reason") or "crm_unavailable"))
        return SimpleNamespace(customer=SimpleNamespace(customer_id=r["customer_id"]))

    def attach_identity(self, *, customer_id: str, **kw: Any) -> None:
        from contracts.customer import CustomerIdentityConflict
        r = self._call(customer_id=customer_id, **kw)
        if not r.get("ok"):
            raise CustomerIdentityConflict(str(r.get("reason")))


def _parts(arg: str, n: int) -> list[str]:
    p = [x.strip() for x in arg.split("|")]
    if len(p) < n or not all(p[:n]):
        raise ValueError("формат: " + " | ".join(["…"] * n))
    return p


def public_event_op(op: str, arg: str, *, body: dict[str, Any], effects: Any, env: Any, facts: Any, done: Any,
                    now_ms: int) -> Any:
    from application.business_flows import event_channels as ec
    from application.business_flows import event_owner_flow as eo
    from application.business_flows import public_events as pe

    tenant_id, user_id = str(body["tenant_id"]), str(body["user_id"])
    platform = str(body.get("channel") or "telegram")
    now = datetime.fromtimestamp(now_ms / 1000, tz=UTC)
    payloads = facts("event_series@v1")
    b = pe.replay(payloads)
    if op == "pub_create":  # title | YYYY-MM-DD HH:MM | Europe/Moscow
        title, when, tz = _parts(arg, 3)[:3]
        from zoneinfo import ZoneInfo
        starts = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
        created, published = eo.create_and_publish(title=title, starts_at=starts, timezone_name=tz, now=now,
                                                   connections=[], notify=False)
        done(f"🗓 Событие создано: {title}", {**created, "created_by_member_id": user_id})
        return done(f"📣 Опубликовано. Регистрация: /event_register {created['slug']} | имя | email", published)
    if op == "pub_register":  # slug | name | email   (consent = sending the command with email)
        slug, name, email = _parts(arg, 3)[:3]
        fact, _token = pe.register(b, slug=slug, name=name, email=email, consent=True, now=now)
        if fact is None:
            return done("ℹ️ Вы уже зарегистрированы.")
        done("✅ Регистрация сохранена.", fact)
        b = pe.replay([*payloads, fact])
        created = next((p for p in payloads if p.get("step") == "pub_event_created"
                        and p.get("event_id") == fact["event_id"]), {})
        creator = str(created.get("created_by_member_id") or "")
        actor = pe.automation_actor([{"member_id": creator, "role": "owner", "status": "active"}] if creator else [],
                                    business_active=True, created_by_member_id=creator or None)
        business_id = str(body.get("business_id") or tenant_id)
        try:
            cid, cf = pe.attach_registration_to_customer(_ExecutorCrm(effects, env), b, fact["registration_id"],
                                                         tenant_id=tenant_id, business_id=business_id,
                                                         email=email, actor=actor)
        except LookupError as exc:
            return done(f"ℹ️ Карточка клиента не создана ({exc}); регистрация действует.")
        if not cid:
            return done("ℹ️ Карточка клиента не создана: нет активного сотрудника; регистрация действует.")
        return done("👤 Клиент привязан к регистрации. Напоминания в мессенджер: /event_links " + slug, cf[0])
    if op == "pub_links":  # slug
        ev = pe.by_slug(b, arg.strip())
        regs = [r for r in b.registrations.values() if r.event_id == ev.event_id and r.status == "registered"
                and r.customer_id and any(p.get("step") == "pub_registration_customer"
                                          and p.get("registration_id") == r.registration_id for p in payloads)]
        if not regs:
            raise ValueError("нет привязанной регистрации")
        tokens, ch = ec.issue_for_registration(b, regs[-1].registration_id, now_ms=now_ms)
        if ch is None:
            raise ValueError("ссылки недоступны")
        rows = "\n".join(f"{p}: /event_verify {ec.PREFIX}{t}" for p, t in tokens.items())
        return done(f"🔗 Ссылки для напоминаний (1 час, одноразовые):\n{rows}", ch)
    if op == "pub_verify":
        ch = ec.consume(payloads, {}, token=ec.extract_token(arg) or "", platform=platform, external_subject=user_id,
                        now_ms=now_ms, registrations=b.registrations)
        return done(f"✅ {platform}: напоминания о событии придут сюда.", ch)
    raise ValueError("unknown op")


def _landing(body, effects, env, facts, slots, arg, done):
    """/landing Название [| раздел | текст | theme x | publish | reset | ai] over event_series@v1 facts."""
    from application.business_flows import admin as ad
    from application.business_flows import bookings as bk
    from application.business_flows import event_landing as el
    from application.business_flows import sales_ai as sa
    from runtime.platform.config.env_flags import env_str

    parts = [x.strip() for x in arg.split("|")]
    title, cmd = parts[0], (parts[1].casefold() if len(parts) > 1 else "")
    ld = el.replay(facts("event_series@v1")).get(el.key_for(title))
    prices = ad.replay(facts("business_admin@v1")).prices
    price = ad.money(*prices[title]) if title in prices else ""
    ordered = sorted(slots.values(), key=lambda x: x.starts_at_ms)
    kw = {"price": price, "fmt_slot": bk.fmt}
    if not cmd:
        return done(el.preview(title, ld, ordered, **kw) + "\n\nПравить: /landing Название | about | текст")
    if cmd == "publish":
        ch = el.publish(title, ld)
        return done("🌐 Лендинг опубликован." if ch else "Эта версия уже опубликована.", ch)
    if cmd == "reset":
        return done("↩️ Лендинг снова по шаблону (публикация не изменена).", el.reset(title))
    if cmd == "theme":
        return done("🎨 Тема сохранена.", el.set_theme(title, parts[2] if len(parts) > 2 else ""))
    if cmd == "ai":
        provider = env_str("MARKETING_LLM_PROVIDER", env_str("LLM_PROVIDER", "")).strip().casefold()
        if provider not in sa.RUSSIAN_PROVIDERS:
            return done("🔒 ИИ-тексты доступны только с YandexGPT или GigaChat (LLM_PROVIDER).")
        system, user = el.ai_prompt(title, el.effective(title, ld, ordered, **kw))
        dec = env.decision
        out = effects.marketing_llm_complete(
            decision_id=str(dec.decision_id),
            correlation_id=str(dec.correlation_id),
            admin_id=str(body.get("user_id") or "owner"),
            system=system,
            user=user,
        )
        if not (isinstance(out, dict) and out.get("ok")):
            return done("⚠️ ИИ сейчас недоступен, попробуйте позже.")
        drafted = el.parse_ai(str(out.get("text") or ""))
        sent = None
        for sec, text in drafted.items():
            sent = done(
                f"🤖 Черновик раздела «{el.SECTION_LABELS[sec]}» сохранён (не опубликован).",
                el.update_section(title, sec, text),
            )
        return sent
    return done(
        "✏️ Раздел сохранён (не опубликован).", el.update_section(title, cmd, parts[2] if len(parts) > 2 else "")
    )


__all__ = ["PUB_OPS", "public_event_op"]
