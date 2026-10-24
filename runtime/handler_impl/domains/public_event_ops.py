"""Public (online) events in the bot: create/publish, register, CRM projection, reminder links.

Ops of event_series@v1. Facts are stored as event_series@v1 tracked payloads (public_events steps are
``pub_*`` / ``channel_*`` and ignored by event_series.replay). CRM writes go only through the executor
effect ``ensure_customer_identity``; reminder links are issued only for CRM-projected registrations.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

PUB_OPS = frozenset({"pub_create", "pub_register", "pub_links", "pub_live", "pub_verify"})
# Real ad spend, business retirement and video: every op is owner-only (route flag) and OFF by default (dry run + event).
SPEND_OPS = frozenset({"spend_prepare", "spend_consent", "spend_launch", "spend_stop", "spend_status", "spend_process",
                       "goal_preview", "retire", "retire_confirm", "retire_cancel", "restore", "video", "event_ads"})
MEDIA_OPS = frozenset({"asset_set", "asset_show", "asset_send", "stage_visual", "gen", "email_connect", "email_verify",
                       "email_test", "adproject", "content_mode"}) | SPEND_OPS
EMAIL_ENV = "BAI_EMAIL_EFFECTS_ENABLED"  # real e-mail sends: off by default, like BAI_PHOTO_DELIVERY_ENABLED


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


def _subject(platform: str, user_id: str) -> str:
    return f"{platform}:{user_id}"


def _registered_by(payloads: list[dict[str, Any]], registration_id: str) -> str:
    """Messenger subject that sent /event_register for this registration ('' for web/legacy registrations)."""
    return next((str(p.get("registered_by") or "") for p in payloads
                 if p.get("step") == "pub_registration" and p.get("registration_id") == registration_id), "")


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
        fact = {**fact, "registered_by": _subject(platform, user_id)}  # owner of /event_links for this registration
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
        mine = _subject(platform, user_id)  # only the registrant's own registration, never another user's
        regs = [r for r in b.registrations.values() if r.event_id == ev.event_id and r.status == "registered"
                and r.customer_id and _registered_by(payloads, r.registration_id) == mine
                and any(p.get("step") == "pub_registration_customer"
                        and p.get("registration_id") == r.registration_id for p in payloads)]
        if not regs:
            raise ValueError("нет вашей привязанной регистрации на это событие: сначала /event_register " + arg.strip())
        tokens, ch = ec.issue_for_registration(b, regs[-1].registration_id, now_ms=now_ms)
        if ch is None:
            raise ValueError("ссылки недоступны")
        rows = "\n".join(f"{p}: /event_verify {ec.PREFIX}{t}" for p, t in tokens.items())
        return done(f"🔗 Ссылки для напоминаний (1 час, одноразовые):\n{rows}", ch)
    if op == "pub_live":  # slug -> owner's exact room links per session
        return done(eo.live_text(eo.live_snapshot(payloads, arg.strip())))
    if op == "pub_verify":
        ch = ec.consume(payloads, {}, token=ec.extract_token(arg) or "", platform=platform, external_subject=user_id,
                        now_ms=now_ms, registrations=b.registrations)
        return done(f"✅ {platform}: напоминания о событии придут сюда.", ch)
    raise ValueError("unknown op")


def _ids(body: dict[str, Any], env: Any) -> dict[str, str]:
    return {"decision_id": str(env.decision.decision_id), "correlation_id": str(env.decision.correlation_id),
            "tenant_id": str(body["tenant_id"])}


def _asset_send(body, effects, env, done, asset, caption, ids):
    """Owner preview of a stored visual. The photo effect is executor-owned and a dry run until the flag is on."""
    if asset is None:
        raise ValueError("визуал не найден: /event_asset ev | stage | slot | image | ref")
    if asset["kind"] != "image":
        return done("ℹ️ Видео хранится как ссылка; отправка видеофайла в чат не подключена (нет исполнителя send_video). "
                    "Создать ролик: /event_video событие | описание.")
    send = getattr(effects, "send_photo", None)
    if send is None:
        return done("🔒 Отправка фото недоступна в этом исполнителе.")
    out = send(**ids, business_id=str(body.get("business_id") or body["tenant_id"]), user_id=str(body["user_id"]),
               path=str(asset["media_reference"]), caption=caption, channel=str(body.get("channel") or "telegram"))
    if not isinstance(out, dict) or not out.get("ok"):
        return done("⚠️ Фото не отправлено: " + str((out or {}).get("reason") or "ошибка доставки"))
    if out.get("status") == "dry_run":
        return done("🔒 Отправка фото выключена (BAI_PHOTO_DELIVERY_ENABLED): показал бы это изображение, но ничего не ушло.")
    return done("🖼 Изображение отправлено.")


def _gen_submit(gens, member, rid, now_ms, put, send):
    """Owner-confirmed submission of ONE prepared receipt: begin (fact) -> executor gateway call -> remember job."""
    import json

    from application.business_flows import visual_creatives as vc

    r = vc.gen_get(gens, member, rid)
    payload = json.loads(r.provider_payload_json)
    if payload.get("kind") != "image":
        raise ValueError("видео создаётся отдельно: /event_video событие | описание")
    r, begin = vc.gen_begin_submission(gens, member, rid, now_ms=now_ms)
    if not begin:
        return put(f"ℹ️ Заявка {r.id} уже в состоянии «{r.status}»: повторная отправка не делается.", [])
    put("⏳ Отправляю заявку в визуальный шлюз…", begin)
    try:
        out = send(prompt=str(payload["brief"]["prompt"]), country_code=str(payload.get("country_code") or r.country_code),
                   brand_context=r.brand_context)
        job = out.get("job") if isinstance(out, dict) else None
    except Exception:  # noqa: BLE001 - outcome unknown: stay "submitting", never resubmit blindly
        job = None
    if not isinstance(job, dict) or not job.get("id"):
        return put("⚠️ Шлюз не подтвердил приём: заявка остаётся «в отправке», повтор запрещён (возможна оплата).", [])
    _, fs = vc.gen_remember_job(gens, member, rid, source_job_id=str(job["id"]), provider_status=str(job.get("status")),
                                provider_error_code=str(job.get("error_code") or ""), now_ms=now_ms)
    return put(f"🖼 Заявка {rid}: задача {job['id']} — {job.get('status')}.", fs)


def _gen_op(arg, gens, member, now_ms, put, send):
    from application.business_flows import visual_creatives as vc

    verb, _, rid = arg.partition(" ")
    verb, rid = verb.strip().casefold(), rid.strip().lower()
    if verb == "submit":
        return _gen_submit(gens, member, rid, now_ms, put, send)
    if verb == "show" and not rid:
        a = vc.gen_active(gens, member)
        return put("🧾 Активной заявки на изображение нет." if a is None else f"🧾 Активная заявка {a.id}: {a.status}", [])
    r = vc.gen_get(gens, member, rid)
    if verb == "show":
        return put(f"🧾 Заявка {r.id}: {r.status}", [])
    steps = {"claim": lambda: vc.gen_claim_delivery(gens, member, rid, now_ms=now_ms),
             "redeliver": lambda: vc.gen_authorize_redelivery(gens, member, rid, now_ms=now_ms),
             "abandon": lambda: vc.gen_abandon(gens, member, rid)}
    if verb == "delivered":
        _, fs = vc.gen_mark_delivered(gens, member, rid, now_ms=now_ms)
        return put("✅ Доставка отмечена.", fs)
    if verb not in steps:
        raise ValueError("формат: /gen show|submit|claim|redeliver|abandon|delivered [id]")
    ok, fs = steps[verb]()
    return put("✅ Готово." if ok else "ℹ️ Без изменений: заявка в другом состоянии.", fs)


def _email_op(op, arg, *, body, effects, env, facts, done, now_ms, put):
    from application.business_flows import native_channels as nc
    from runtime.platform.config.env_flags import env_bool

    conns = nc.email_replay(facts("event_series@v1"))
    if op == "email_connect":  # sender | host | port | username_ref | password_ref | ssl|starttls | name
        p = [x.strip() for x in arg.split("|")]
        if len(p) < 5:
            raise ValueError("формат: /email_connect from@x.ru | smtp.x.ru | 465 | env:SMTP_USER | env:SMTP_PASS | ssl")
        conn, fs = nc.provision_email_smtp(sender_email=p[0], smtp_host=p[1], smtp_port=int(p[2]), username_ref=p[3],
                                           password_ref=p[4], security=p[5] if len(p) > 5 and p[5] else "ssl",
                                           sender_name=p[6] if len(p) > 6 else "")
        return put(f"📧 Подключение {conn.id} сохранено как «ожидает проверки» (пароль не хранится, только ссылка). "
                   f"Проверить: /email_verify {conn.id}", fs)
    if op == "email_verify":
        if not env_bool(EMAIL_ENV, False):
            return put(f"🔒 Проверка SMTP выключена ({EMAIL_ENV}): подключение осталось «ожидает проверки».", [])
        probe = getattr(effects, "email_smtp_probe", None)
        if probe is None:
            return put("🔒 SMTP-проверка недоступна в этом исполнителе: подключение осталось «ожидает проверки».", [])
        _, fs = nc.verify_and_activate_email_smtp(conns, arg.strip(), lambda c: _probe(probe, c, body, env))
        return put("✅ SMTP принят, подключение активно.", fs)
    cid, to, subject, text = (x.strip() for x in (arg.split("|") + ["", "", "", ""])[:4])  # email_test
    target = None if not (to and subject and text) else es_target(conns, cid, to)
    if target is None:
        raise ValueError("формат: /email_test conn_id | кому | тема | текст (подключение должно быть активным)")
    if not env_bool(EMAIL_ENV, False):
        return put(f"🔒 Отправка писем выключена ({EMAIL_ENV}): письмо «{subject}» для {to} записано, но не отправлено.",
                   [{"step": "email_dry_run", "connection_id": cid, "to": to, "subject": subject}])
    out = effects.send_message(**_ids(body, env), user_id=to, text=text, subject=subject, channel="email",
                               business_id=str(body.get("business_id") or body["tenant_id"]))
    sent = not (isinstance(out, dict) and out.get("ok") is False)
    return put("📨 Письмо передано исполнителю." if sent else "⚠️ Письмо не отправлено.",
               [{"step": "email_sent", "connection_id": cid, "to": to, "subject": subject}] if sent else [])


def _probe(probe: Any, conn: Any, body: dict[str, Any], env: Any) -> None:
    out = probe(**_ids(body, env), connection_id=conn.id, host=conn.host, port=conn.port, security=conn.security,
                username_ref=conn.username_ref, password_ref=conn.password_ref, sender_email=conn.sender_email)
    if not (isinstance(out, dict) and out.get("ok")):
        raise ValueError("SMTP отклонил учётные данные")


def es_target(conns: dict[str, Any], connection_id: str, email: str) -> dict[str, Any] | None:
    from application.business_flows import event_series as es

    return es.resolve_email_target(conns, email_connection_id=connection_id, email=email)


def _adproject_op(arg, *, body, effects, env, facts, done, now_ms, put):
    from application.business_flows import ad_media as am
    from application.business_flows import ad_proposals as ap

    member, verb, _, rest = str(body["user_id"]), *arg.partition(" ")
    projects = am.eap_replay(facts("event_series@v1"))
    drafts = ap.replay(facts("business_admin@v1"))

    def pub(job_id: str) -> str | None:
        d = drafts.get(job_id)
        return None if d is None else {"blocked": "failed"}.get(d.status, "draft")

    p = [x.strip() for x in rest.split("|")]
    verb = verb.casefold()
    if verb == "create":  # pub_job | kind | headline | body [| cta | layout | font]
        if len(p) < 4:
            raise ValueError("формат: /adproject create draft_id | image | заголовок | текст [| CTA | lower_card | auto]")
        v, fs = am.create_project(projects, member, publication_job_id=p[0], publication_status=pub(p[0]), kind=p[1],
                                  headline=p[2], body=p[3], brand={}, cta=p[4] if len(p) > 4 else "Записаться",
                                  layout=p[5] if len(p) > 5 and p[5] else "lower_card",
                                  preset=p[6] if len(p) > 6 and p[6] else "auto", now_ms=now_ms)
        return put(f"🎨 Проект {v.id}: «{v.headline}» ({v.status}, r{v.revision})", fs)
    pid = p[0]
    v = am.get_project(projects, member, pid)
    if verb == "show":
        return put(f"🎨 Проект {v.id}: {v.status}, r{v.revision}, источник: {v.source_job_id or '—'}", [])
    kw = {"publication_status": pub(v.publication_job_id), "now_ms": now_ms}
    if verb == "edit":  # id | headline | body | cta | layout | font   (empty = keep)
        f = dict(zip(("headline", "body", "cta", "layout", "preset"), (x or None for x in p[1:6]), strict=False))
        v, fs = am.update_composition(projects, member, pid, **f, **kw)
    elif verb == "bind":
        v, fs = am.bind_source(projects, member, pid, p[1] if len(p) > 1 else "", **kw)
    elif verb == "new_source":
        v, fs = am.prepare_source(projects, member, pid, **kw)
    elif verb == "finish":
        v, fs = am.finish_project(projects, member, pid, **kw)
    elif verb == "render":
        return _adproject_render(v, p, projects, member, body, effects, env, done, now_ms, put)
    else:
        raise ValueError("формат: /adproject create|show|edit|bind|new_source|finish|render ...")
    return put(f"🎨 Проект {v.id}: {v.status}, r{v.revision}", fs)


def _adproject_render(v, p, projects, member, body, effects, env, done, now_ms, put):
    from application.business_flows import ad_media as am

    formats = am.render_formats(tuple(x for x in (p[1].split(",") if len(p) > 1 else ()) if x) or ("square",))
    poll = getattr(effects, "poll_visual_creative", None)
    if v.status == "source_expired":
        raise ValueError(f"источник устарел: /adproject new_source {v.id}")
    if not v.source_job_id or poll is None:
        raise ValueError("источник изображения не привязан или шлюз недоступен")
    job = poll(**_ids(body, env), user_id=str(body["user_id"]), job_id=v.source_job_id)
    try:
        am.render_check(v, job_status=str(job.get("status")), asset_ready=bool(job.get("asset_ready")),
                        job_kind=str(job.get("kind")))
    except am.EditableAdSourceExpired as exc:
        _, fs = am.mark_expired(projects, member, v.id, expected_source_job_id=v.source_job_id, now_ms=now_ms)
        return put(f"⚠️ Источник устарел ({exc}). Новый источник: /adproject new_source {v.id}", fs)
    except am.EditableAdError as exc:
        return put(f"⚠️ Рендер не готов: {exc}", [])
    return put(f"🎨 Источник готов, ключ рендера {am.render_key(v, formats)[-12:]}. Наложение текста выполняет "
               "визуальный шлюз (в этом порте не подключено).", [])


def media_op(op: str, arg: str, *, body: dict[str, Any], effects: Any, env: Any, facts: Any, done: Any, now_ms: int) -> Any:
    """Photo/e-mail/visual-asset ops of event_series@v1. Facts only; every send is an executor effect behind a flag."""
    from application.business_flows import event_series as es
    from application.business_flows import visual_creatives as vc

    member, business_id = str(body["user_id"]), str(body.get("business_id") or body["tenant_id"])
    payloads = es.expand(facts("event_series@v1"))
    st = es.replay(payloads)

    def put(text: str, fs: list[dict[str, Any]]) -> Any:
        return done(text, *([] if not fs else [fs[0] if len(fs) == 1 else {"step": "batch", "facts": fs}]))

    try:
        if op in SPEND_OPS:
            return spend_op(op, arg, body=body, effects=effects, env=env, payloads=payloads, put=put, now_ms=now_ms)
        if op in {"asset_set", "asset_show", "asset_send"}:  # ev | stage | slot [| kind | media_reference]
            p = _parts(arg, 3)
            ev, stage, slot = p[:3]
            if op == "asset_set":
                if len(p) < 5:
                    raise ValueError("формат: /event_asset ev | stage | slot | image|video | ссылка_на_файл")
                a, fs = es.set_asset_reference(st, event_id=ev, stage=stage, slot_key=slot, kind=p[3],
                                               media_reference=p[4], source="owner")
                return put(f"🖼 Визуал сохранён (ревизия {a['revision']}).", fs)
            a = es.get_asset(st, ev, stage, slot)
            if op == "asset_show":
                return put("ℹ️ Визуала нет." if a is None else f"🖼 {a['kind']}, ревизия {a['revision']}, источник {a['source']}", [])
            return _asset_send(body, effects, env, done, a, None, _ids(body, env))
        if op == "content_mode":  # ev | stage | text|text_with_image|text_in_image
            ev, stage, mode = _parts(arg, 3)[:3]
            if mode == "text_with_video" and vc.video_generation_mode() != "motion":
                raise ValueError(f"видео выключено: включите {vc.VIDEO_ENV} (только российский провайдер yandexart_motion)")
            ch = es.set_content_mode(ev, stage, mode)
            return put(f"🧩 Формат сообщения этапа «{stage}»: {mode}", [ch])
        if op == "stage_visual":  # ev | stage | message_key | title | text
            ev, stage, key, title, text = _parts(arg, 5)[:5]
            gens = vc.gen_replay(payloads)
            brand = [x for x in payloads if str(x.get("step", "")).startswith("brand")]
            res, fs = es.prepare_stage_visual(st, gens, member, business_id=business_id, brand_facts=brand, event_id=ev,
                                              stage=stage, message_key=key, event_title=title, message_text=text, now_ms=now_ms)
            if res is None:
                return put("ℹ️ Для этого этапа выбран «только текст»: визуал не нужен.", [])
            return put(f"🧾 Заявка {res['receipt_id']} подготовлена. Генерация НЕ запускалась: нужно отдельное "
                       "подтверждение владельца и исполнитель.", fs)
        if op == "gen":
            def send(**kw):
                return effects.generate_visual_creative(**_ids(body, env), user_id=member, kind="image", **kw)

            return _gen_op(arg, vc.gen_replay(payloads), member, now_ms, put, send)
        if op == "adproject":
            return _adproject_op(arg, body=body, effects=effects, env=env, facts=facts, done=done, now_ms=now_ms, put=put)
        return _email_op(op, arg, body=body, effects=effects, env=env, facts=facts, done=done, now_ms=now_ms, put=put)
    except (ValueError, LookupError, es.AssetBindError, RuntimeError) as exc:
        return done(f"⚠️ Не получилось: {exc}")


class _ExecutorAdProvider:
    """AdProviderPort-shaped adapter over the executor effect. Credentials live in the executor transport (env:/vault:
    refs resolved there); nothing here ever sees a token. A dry run maps to ProviderReadError/{"dry_run": True}."""

    def __init__(self, effects: Any, body: dict[str, Any], env: Any) -> None:
        self._fx, self._body, self._env = effects, body, env

    def _act(self, action: str, params: dict[str, Any], key: str = "") -> dict[str, Any]:
        return self._fx.ad_provider_action(**_ids(self._body, self._env), user_id=str(self._body["user_id"]), action=action,
                                           params=params, idempotency_key=key)

    def _checked(self, out: dict[str, Any]) -> dict[str, Any]:
        from application.business_flows import ad_spend_guard as sg

        if out.get("status") == "dry_run":
            raise sg.ProviderReadError("provider_dry_run")
        if not out.get("ok"):
            if out.get("status") in {"unconfigured", "refused"}:  # never retried: nothing was sent
                raise sg.SpendInvariantViolation(str(out.get("error") or out.get("status")))
            raise sg.ProviderReadError(str(out.get("error") or "provider_error")[:60])
        return dict(out.get("result") or {})

    def refresh(self, bundle: Any) -> dict[str, str]:
        return dict(bundle)

    def read_budget(self, access_token: str, *, campaign_id: str, report_date: str, now: Any) -> Any:
        from application.business_flows import ad_spend_guard as sg

        r = self._checked(self._act("read_budget", {"campaign_id": campaign_id, "report_date": report_date}))
        names = ("external_account_id", "external_campaign_id", "currency", "strategy", "report_date")
        try:
            return sg.BudgetReadout(**{k: str(r[k]) for k in names},
                                    **{k: int(r.get(k) or 0) for k in ("available_budget_minor", "spent_today_minor",
                                                                      "minimum_weekly_micros")},
                                    launch_eligible=bool(r.get("launch_eligible", True)))
        except (KeyError, TypeError, ValueError) as exc:
            raise sg.ProviderReadError("provider_readout_invalid") from exc

    def _mutate(self, action: str, params: dict[str, Any], key: str) -> dict[str, Any]:
        out = self._act(action, params, key)
        return {"dry_run": True, "action": action} if out.get("status") == "dry_run" else self._checked(out)

    def configure_budget(self, access_token: str, *, campaign_id: str, hard_cap_minor: int, daily_cap_minor: int,
                         idempotency_key: str) -> dict[str, Any]:
        return self._mutate("configure_budget", {"campaign_id": campaign_id, "hard_cap_minor": hard_cap_minor,
                                                 "daily_cap_minor": daily_cap_minor}, idempotency_key)

    def moderate_ad(self, access_token: str, *, campaign_id: str, idempotency_key: str) -> dict[str, Any]:
        return self._mutate("moderate_ad", {"campaign_id": campaign_id}, idempotency_key)

    def suspend_ad(self, access_token: str, *, campaign_id: str, idempotency_key: str) -> dict[str, Any]:
        return self._mutate("suspend_ad", {"campaign_id": campaign_id}, idempotency_key)


def _spend_process(payloads, provider, tz, now, put, text, pre=()):
    """Run due queue operations (at most 4 per call); every provider mutation is gated by executor flags."""
    from application.business_flows import ad_spend_guard as sg

    recorded: list[dict[str, Any]] = list(pre)
    for _ in range(4):
        fs = sg.process_one_operation([*payloads, *recorded], provider, {"access_token": "executor"}, tz=tz, now=now)
        if not fs:
            break
        recorded += fs
    done_ops = [f for f in recorded if f["step"] == "ad_spend_op_completed"]
    failed = [f for f in recorded if f["step"] == "ad_spend_op_failed"]
    note = ("⏳ Очередь пуста." if not (recorded[len(pre):]) else
            ("🔒 Провайдер в пробном режиме (флаги выключены): ничего не отправлено и не потрачено."
             if any((f.get("evidence") or {}).get("dry_run") for f in done_ops) else
             f"✅ Выполнено операций: {len(done_ops)}." if done_ops and not failed else
             "⚠️ Операция не выполнена: " + ", ".join(sorted({str(f.get("code")) for f in failed})) + ". Ничего не потрачено сверх проверенных лимитов."))
    return put((text + "\n" if text else "") + note, recorded)


def spend_op(op: str, arg: str, *, body: dict[str, Any], effects: Any, env: Any, payloads: list[dict[str, Any]], put: Any,
             now_ms: int) -> Any:
    """Owner-only spend / retire / video ops. All OFF by default; DecisionCore decides, only the executor acts."""
    import uuid

    from application.business_flows import ad_spend_guard as sg
    from application.business_flows import admin as ad
    from application.business_flows import event_consent as ecn
    from application.business_flows import public_events as pe
    from application.business_flows import visual_creatives as vc

    now = datetime.fromtimestamp(now_ms / 1000, tz=UTC)
    business_id = str(body.get("business_id") or body["tenant_id"])
    provider = _ExecutorAdProvider(effects, body, env)
    archived = ad.is_archived(payloads)
    auths = sg.authorizations_replay(payloads)

    def auth_of(token: str) -> Any:
        base = auths.get(token.strip())
        if base is None:
            raise ValueError("разрешение не найдено: /ad_spend_status")
        return sg.with_status(payloads, base)

    def refuse_if_archived() -> None:
        if archived:
            raise ValueError("бизнес в архиве: расходы на рекламу запрещены (вернуть: /business_restore)")

    def stops(reason: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for a in auths.values():
            out += sg.revoke_consent(payloads, a, actor_member_id=str(body["user_id"]), now=now) if \
                sg.consent_status(payloads, a) in {"launching", "active", "stopping"} else []
        return [{**f, "reason": reason} if f["step"] == "ad_spend_stop_queued" else f for f in out]

    if op == "spend_status":
        rows = sg.consent_view(payloads, auths.values())
        return put("💳 Разрешения на рекламу:\n" + ("\n".join(
            f"• {r['authorization_id']}: {r['status']}, лимит {r['hard_cap_minor']}/день {r['daily_cap_minor']} {r['currency']}"
            for r in rows) or "Пока нет. Подготовить: /ad_spend_prepare") + ("\n📦 Бизнес в архиве." if archived else ""), [])
    if op == "goal_preview":  # connection | campaign
        conn, camp = _parts(arg, 2)[:2]
        pv = sg.preview_goal_spend(provider, {"access_token": "executor"}, connection_id=conn, campaign_id=camp, now=now,
                                   tz=sg.report_timezone())
        return put(f"🎯 Предпросмотр (ничего не запущено): жёсткий лимит {pv.recommended_hard_cap_minor}, в день "
                   f"{pv.recommended_daily_cap_minor} {pv.currency} (доступно {pv.available_budget_minor}).", [])
    if op == "spend_prepare":  # connection | account | campaign | hard | daily | minutes
        refuse_if_archived()
        conn, acct, camp, hard, daily, mins = _parts(arg, 6)[:6]
        tz = sg.report_timezone()
        auth, fact = sg.prepare_authorization(
            provider, {"access_token": "executor"}, business_id=business_id, connection_id=conn, external_account_id=acct,
            external_campaign_id=camp, hard_cap_minor=int(hard), daily_cap_minor=int(daily),
            expires_at=now + timedelta(minutes=max(1, min(int(mins), 5))), report_date=sg.provider_report_date(now, tz),
            tz=tz, now=now)
        ask = sg.request_consent(payloads, auth, now=now)
        return put(f"💳 Разрешение {auth.authorization_id} подготовлено: до {auth.hard_cap_minor} (в день {auth.daily_cap_minor}) "
                   f"{auth.currency}, действует до {auth.expires_at:%H:%M} UTC. Деньги НЕ потрачены.\n"
                   f"Подтвердить именно эти условия: /ad_spend_consent {auth.authorization_id} | {ask['terms_hash'][:16]}", [fact, ask])
    if op == "spend_consent":  # authorization | terms_hash_prefix
        refuse_if_archived()
        token, prefix = _parts(arg, 2)[:2]
        auth, shown = auth_of(token), next((f for f in payloads if f.get("step") == "ad_spend_consent_requested"
                                            and f.get("authorization_id") == token.strip()), None)
        if shown is None or len(prefix) < 12 or not str(shown["terms_hash"]).startswith(prefix):
            raise ValueError("хэш условий не совпал: подтверждайте ровно показанные условия")
        fact = sg.grant_consent(payloads, auth, expected_terms_hash=shown["terms_hash"],
                                expected_snapshot_hash=shown["snapshot_hash"], receipt_id=str(env.decision.decision_id), now=now)
        return put(f"✅ Согласие записано. Запуск — отдельным шагом: /ad_spend_launch {auth.authorization_id}", [fact])
    if op == "spend_launch":
        refuse_if_archived()
        auth = auth_of(arg)
        fact = sg.launch_or_dry_run(payloads, auth, now=now)
        if fact["step"] == "ad_spend_launch_dry_run":
            return put(sg.launch_message("dry_run"), [fact])
        return _spend_process([*payloads, fact], provider, sg.report_timezone(), now, put,
                              sg.launch_message("queued", sg.op_id(auth.authorization_id, "launch")))
    if op == "spend_stop":  # always allowed, also when archived
        auth = auth_of(arg)
        fs = [] if auth.status in {"stopped", "failed"} else sg.revoke_consent(
            payloads, auth, actor_member_id=str(body["user_id"]), now=now)
        if not fs:
            return put("ℹ️ Разрешение уже отозвано.", [])
        return _spend_process([*payloads, *fs], provider, sg.report_timezone(), now, put, "🛑 Разрешение отозвано.") \
            if any(f["step"] == "ad_spend_stop_queued" for f in fs) else put("🛑 Разрешение отозвано.", fs)
    if op == "spend_process":
        return _spend_process(payloads, provider, sg.report_timezone(), now, put, "")
    if op in {"retire", "retire_confirm", "retire_cancel", "restore"}:
        if op == "retire":
            name = arg.strip() or ad.replay(payloads).settings.get("business_name", "") or business_id
            fact, code = ad.retire_request(payloads, name=name, nonce=uuid.uuid4().hex[:8], now=now)
            return put(ad.retire_confirm_text(name, code), [fact])
        if op == "retire_confirm":
            fact = ad.retire_confirm(payloads, code=arg.strip(), now=now)
            if fact is None:
                return put("ℹ️ Бизнес уже в архиве.", [])
            if fact["step"] == "business_retire_dry_run":
                return put(ad.retire_result_text(ad.retire_status(payloads, now)["name"], dry_run=True), [fact])
            text = ad.retire_result_text(ad.retire_status(payloads, now)["name"], dry_run=False)
            stp = stops("business_archived")
            if not stp:
                return put(text, [fact])
            return _spend_process(payloads, provider, sg.report_timezone(), now, put,
                                  text + "\n🛑 Рекламные разрешения отозваны.", pre=[fact, *stp])
        fact = (ad.retire_cancel if op == "retire_cancel" else ad.business_restore)(payloads, now)
        if fact is None:
            return put("ℹ️ Нечего менять.", [])
        return put("↩️ Закрытие отменено." if op == "retire_cancel" else "📦➡️ Бизнес возвращён из архива, данные целы.", [fact])
    if op == "event_ads":  # slug
        b = pe.replay(payloads)
        ev = pe.by_slug(b, arg.strip())
        url = ecn.registration_url(public_base_url=os.environ.get("PUBLIC_BASE_URL", ""), public_slug=ev.slug, source="ads",
                                   campaign_ref=ev.slug[:40])
        return put(sg.event_promotion_message(ev.title, url), [])
    if op == "video":  # event | description
        refuse_if_archived()
        ev, prompt = _parts(arg, 2)[:2]
        frozen = vc.freeze_video_payload(request=prompt, brand_context=f"событие {ev}", preferred_provider="yandexart_motion")
        key = vc.video_idempotency_key(business_id, frozen)
        if (prior := vc.video_already_requested(payloads, key)) is not None:
            return put(f"ℹ️ Ролик уже заказан (задание {prior['job_id'] or '—'}): повторно не отправляю.", [])

        class _Video(vc.VideoProviderPort):
            def submit(self, *, prompt, aspect_ratio, duration_seconds, preferred_provider, idempotency_key):  # noqa: ANN001
                out = effects.generate_visual_creative(**_ids(body, env), user_id=str(body["user_id"]), kind="video",
                                                       prompt=prompt, aspect_ratio=aspect_ratio, duration_seconds=duration_seconds,
                                                       preferred_provider=preferred_provider, wait_seconds=0)
                job = out.get("job") or {}
                return {"ok": bool(out.get("ok")), "status": str(out.get("status") or job.get("status") or ""),
                        "job_id": str(job.get("id") or ""), "reason": str(out.get("reason") or "")}

        out = vc.create_video_from_frozen_payload(provider_payload_json=frozen, scope_id=business_id, idempotency_key=key,
                                                  provider=_Video())
        fact = vc.video_requested_fact(business_id, frozen, out, now_ms=now_ms)
        return put(f"🔒 Видео выключено ({vc.VIDEO_ENV}): записано как пробный запуск, провайдер не вызывался." if fact["dry_run"]
                   else f"🎬 Ролик заказан (российский провайдер), задание {out.get('job_id') or '—'}.", [fact])
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


__all__ = ["MEDIA_OPS", "PUB_OPS", "SPEND_OPS", "media_op", "public_event_op", "spend_op"]
