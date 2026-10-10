from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.business_autonomy.provider_catalog import BRIDGE_MESSAGING_PROVIDER_KEYS, provider_map
from application.business_autonomy.provider_truth_matrix import provider_truth_map

CANON_PUBLIC_SITE_CTA_INTAKE = True
CANON_PUBLIC_SITE_USER_ONBOARDING_VIEW = True
CANON_PUBLIC_SITE_INTEGRATION_MARKETPLACE = True

_AUTONOMY_LABELS = {"advisor": "Советник", "assistant": "Помощник", "autopilot": "Автопилот"}
_PUBLIC_PROVIDERS = (
    "telegram_bot", "whatsapp_cloud", "email_connector", "sms_connector", *tuple(sorted(BRIDGE_MESSAGING_PROVIDER_KEYS)), "generic_website", "wordpress", "webflow",
    "shopify", "woocommerce", "hubspot", "ozon_marketplace", "wildberries_marketplace", "amazon_marketplace",
    "ebay_marketplace", "etsy_marketplace", "google_ads", "meta_ads", "tiktok_ads", "call_tracking",
)
_RECOMMENDED = {"telegram_bot", "generic_website", "hubspot", "ozon_marketplace", "wildberries_marketplace"}
_CONNECTION_MODES = {"telegram_bot": "provider_native_api", "whatsapp_cloud": "provider_webhook_and_cloud_api", "email_connector": "smtp_outbound", "sms_connector": "vendor_selection_required", "generic_website": "web_ingress", "vk_messaging": "native_vk_callback_or_provider_webhook_bridge", "max_messaging": "native_max_api_or_provider_webhook_bridge", "slack_messaging": "native_slack_events_or_provider_webhook_bridge", "discord_messaging": "native_discord_http_or_provider_webhook_bridge", "instagram_messaging": "native_instagram_send_api_or_provider_webhook_bridge", "messenger_messaging": "native_messenger_send_api_or_provider_webhook_bridge", "line_messaging": "native_line_messaging_api_or_provider_webhook_bridge", "viber_messaging": "native_viber_bot_api_or_provider_webhook_bridge"}
_GOAL_CHECKS = {
    "growth": ("потерянные лиды", "каналы с лучшей конверсией", "точки роста повторных продаж"),
    "retention": ("клиенты без повторной покупки", "незавершённые диалоги", "сегменты для реактивации"),
    "ads_efficiency": ("кампании с неэффективным расходом", "стоимость привлечения", "расхождения атрибуции"),
    "operations": ("ручные повторяющиеся операции", "очереди без владельца", "задержки исполнения"),
    "sales": ("зависшие сделки", "пропущенные follow-up", "воронка по источникам"),
}


@dataclass(frozen=True)
class CTASubmitResult:
    intake_id: str
    created_at: str
    app_url: str
    outcome: str = "intake_recorded"
    tenant_id: str = ""
    business_id: str = ""
    user_id: str = ""
    owner_account_id: str = ""
    onboarding_status: str = "advisory_intake_created"
    next_actions: tuple[dict[str, object], ...] = ()
    user_functionality: dict[str, object] | None = None
    admin_visibility: dict[str, object] | None = None
    business_profile: dict[str, object] | None = None
    selected_providers: tuple[str, ...] = ()
    integration_plan: tuple[dict[str, object], ...] = ()
    autonomy_mode: str = "advisor"
    first_value_preview: dict[str, object] | None = None
    onboarding_progress: dict[str, object] | None = None


@dataclass(frozen=True)
class CTAIntakeStatus:
    intake_id: str
    found: bool
    outcome: str
    created_at: str
    tenant_id: str = ""
    business_id: str = ""
    user_id: str = ""
    owner_account_id: str = ""
    onboarding_status: str = "not_found"
    next_actions: tuple[dict[str, object], ...] = ()
    user_functionality: dict[str, object] | None = None
    admin_visibility: dict[str, object] | None = None
    business_profile: dict[str, object] | None = None
    selected_providers: tuple[str, ...] = ()
    integration_plan: tuple[dict[str, object], ...] = ()
    autonomy_mode: str = "advisor"
    first_value_preview: dict[str, object] | None = None
    onboarding_progress: dict[str, object] | None = None


def public_integration_marketplace() -> tuple[dict[str, object], ...]:
    providers, truth = provider_map(), provider_truth_map()
    rows = []
    for key in _PUBLIC_PROVIDERS:
        provider, state = providers.get(key), truth.get(key)
        if provider is None or state is None:
            continue
        selectable = bool(state.read_only_supported)
        availability = "available_read_only" if selectable else ("preparing" if state.status in {"implemented", "partial"} else "roadmap")
        label = {"available_read_only": "Можно подключить для анализа", "preparing": "Подключение готовится", "roadmap": "Скоро"}[availability]
        rows.append({
            "provider_key": key, "title": provider.title, "category": provider.domain, "description": provider.description,
            "status": state.status, "availability": availability, "availability_label": label, "selectable": selectable,
            "read_supported": selectable, "write_supported": False, "approval_required": bool(state.approval_required),
            "risk_level": state.risk_level, "recommended": key in _RECOMMENDED, "connection_mode": _CONNECTION_MODES.get(key, "provider_webhook_bridge" if key in BRIDGE_MESSAGING_PROVIDER_KEYS else "provider_native_or_managed"),
            "credential_labels": [field.label for field in provider.secret_fields if field.required],
            "read_capabilities": list(state.read_capabilities),
            "note": "Внешние write-действия выключены до отдельного подтверждения и evidence guard.",
        })
    return tuple(rows)



@contextmanager
def _intake_lock(path: Path):
    """Serialize CTA and settings appends across API workers on the same ledger."""
    path.parent.mkdir(parents=True, exist_ok=True)
    guard_path = path.with_name(path.name + ".lock")
    with guard_path.open("a+b") as guard:
        if os.name == "nt":
            import msvcrt
            guard.seek(0, os.SEEK_END)
            if guard.tell() == 0:
                guard.write(b"\x00")
                guard.flush()
            guard.seek(0)
            msvcrt.locking(guard.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                guard.seek(0)
                msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(guard.fileno(), fcntl.LOCK_UN)


def _append_intake_row(path: Path, row: dict[str, object]) -> None:
    """Caller holds _intake_lock; never create a parallel settings store."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _latest_business_row(lines, *, tenant_id: str, business_id: str) -> dict[str, object]:
    for line in reversed(lines):
        try:
            row = json.loads(line) if line.strip() else None
        except (json.JSONDecodeError, TypeError):
            continue
        if (
            isinstance(row, dict)
            and str(row.get("tenant_id") or "") == tenant_id
            and str(row.get("business_id") or "") == business_id
            and str(row.get("intake_id") or "").strip()
        ):
            return row
    raise KeyError("business_settings_not_found")


def _settings_payload(row: dict[str, object]) -> dict[str, object]:
    profile = dict(row.get("business_profile") or {})
    settings = dict(row.get("business_settings") or {})
    return {
        "tenant_id": str(row.get("tenant_id") or ""),
        "business_id": str(row.get("business_id") or ""),
        "business_name": str(profile.get("name") or ""),
        "activity_description": str(settings.get("activity_description") or ""),
        "timezone_name": str(settings.get("timezone_name") or "Europe/Moscow"),
        "revision": int(row.get("settings_revision") or 0),
        "updated_at": str(row.get("settings_updated_at") or row.get("created_at") or ""),
    }


def _validate_business_settings(*, business_name: str, activity_description: str, timezone_name: str) -> tuple[str, str, str]:
    if not all(isinstance(value, str) for value in (business_name, activity_description, timezone_name)):
        raise ValueError("business_settings_fields_must_be_strings")
    name, activity, tz = business_name.strip(), activity_description.strip(), timezone_name.strip()
    if not 1 <= len(name) <= 200 or len(activity) > 2000 or not 1 <= len(tz) <= 120:
        raise ValueError("business_settings_fields_invalid")
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("business_settings_timezone_invalid") from exc
    return name, activity, tz


class CTALandingIntakeService:
    def __init__(self, *, storage_path: str = "runtime_state/pilot_applications.jsonl", app_base_url: str = "https://app.businessaios.ru") -> None:
        self._storage_path, self._app_base_url = Path(storage_path), app_base_url.rstrip("/")

    def submit(self, *, payload: dict[str, object], owner_account_id: str | None = None, owner_subject: str | None = None) -> CTASubmitResult:
        data, intake_id = dict(payload or {}), f"cta-{uuid4().hex[:16]}"
        profile, selected, autonomy = _business_profile(data), _selected_providers(data), _autonomy_mode(data)
        tenant_id = _stable_id("tenant", intake_id)
        business_id = _stable_id("business", intake_id)
        account_id = str(owner_account_id or "").strip() or _stable_id("owner", intake_id)
        user_id = str(owner_subject or "").strip() or _stable_id("user", intake_id)
        result = CTASubmitResult(
            intake_id=intake_id, created_at=datetime.now(UTC).isoformat(), app_url=f"{self._app_base_url}/?intake_id={intake_id}",
            tenant_id=tenant_id, business_id=business_id, user_id=user_id, owner_account_id=account_id, business_profile=profile,
            selected_providers=selected, integration_plan=_integration_plan(selected), autonomy_mode=autonomy,
            first_value_preview=_first_value(profile, selected), onboarding_progress=_progress(profile, selected, autonomy),
            next_actions=_next_actions(intake_id, tenant_id, business_id, selected),
            user_functionality=_user_functionality(intake_id, tenant_id, business_id, user_id, autonomy, selected),
            admin_visibility=_admin_visibility(intake_id, tenant_id, business_id, user_id),
        )
        row = asdict(result)
        row.pop("app_url", None)
        row.update({
            "source": "public_landing_cta", "payload": data,
            "canonical_flow": {"stage": "self_service_read_only_onboarding", "write_actions_enabled": False,
                               "requires_approval_before_execution": True, "decision_core_required_for_irreversible_actions": True,
                               "credential_activation_requires_authenticated_control_plane": True},
        })
        with _intake_lock(self._storage_path):
            _append_intake_row(self._storage_path, row)
        return result

    def get_status(self, *, intake_id: str) -> CTAIntakeStatus:
        token = str(intake_id or "").strip()
        if not token or not self._storage_path.exists():
            return CTAIntakeStatus(token, False, "not_found", "")
        for line in reversed(self._storage_path.read_text(encoding="utf-8").splitlines()):
            try:
                row = json.loads(line) if line.strip() else None
            except Exception:
                continue
            if isinstance(row, dict) and str(row.get("intake_id") or "") == token:
                return _status_from_row(token, row)
        return CTAIntakeStatus(token, False, "not_found", "")

    def list_recent(self, *, limit: int = 50) -> tuple[dict[str, object], ...]:
        if not self._storage_path.exists():
            return ()
        rows, seen = [], set()
        for line in reversed(self._storage_path.read_text(encoding="utf-8").splitlines()):
            if len(rows) >= max(1, min(int(limit or 50), 200)):
                break
            try:
                row = json.loads(line) if line.strip() else None
            except Exception:
                continue
            if isinstance(row, dict):
                intake_id = str(row.get("intake_id") or "").strip()
                if not intake_id or intake_id in seen:
                    continue
                seen.add(intake_id)
                rows.append(_admin_row(row))
        return tuple(rows)

    def list_owner_businesses(self, *, owner_account_id: str, limit: int = 100) -> tuple[dict[str, object], ...]:
        account_id = str(owner_account_id or "").strip()
        if not account_id or not self._storage_path.exists():
            return ()
        rows, seen = [], set()
        for line in reversed(self._storage_path.read_text(encoding="utf-8").splitlines()):
            if len(rows) >= max(1, min(int(limit or 100), 200)):
                break
            try:
                row = json.loads(line) if line.strip() else None
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            intake_id = str(row.get("intake_id") or "").strip()
            if not intake_id or intake_id in seen:
                continue
            seen.add(intake_id)
            if _row_owner_account_id(row) != account_id:
                continue
            profile = dict(row.get("business_profile") or {}) if isinstance(row.get("business_profile"), dict) else _business_profile(dict(row.get("payload") or {}))
            rows.append({
                "intake_id": intake_id, "tenant_id": str(row.get("tenant_id") or ""), "business_id": str(row.get("business_id") or ""),
                "name": str(profile.get("name") or "Бизнес"), "industry": str(profile.get("industry") or ""), "city": str(profile.get("city") or ""),
                "website": str(profile.get("website") or ""), "goal": str(profile.get("goal") or "growth"),
                "autonomy_mode": str(row.get("autonomy_mode") or "advisor"), "created_at": str(row.get("created_at") or ""),
                "onboarding_status": str(row.get("onboarding_status") or "advisory_intake_created"),
            })
        return tuple(rows)


    def read_business_settings(self, *, tenant_id: str, business_id: str) -> dict[str, object]:
        tenant, business = str(tenant_id or "").strip(), str(business_id or "").strip()
        if not tenant or not business or not self._storage_path.exists():
            raise KeyError("business_settings_not_found")
        row = _latest_business_row(
            self._storage_path.read_text(encoding="utf-8").splitlines(),
            tenant_id=tenant, business_id=business,
        )
        return _settings_payload(row)

    def update_business_settings(
        self, *, tenant_id: str, business_id: str,
        business_name: str, activity_description: str, timezone_name: str,
        expected_revision: int, idempotency_key: str, actor_id: str = "",
    ) -> dict[str, object]:
        tenant, business = str(tenant_id or "").strip(), str(business_id or "").strip()
        name, activity, timezone = _validate_business_settings(
            business_name=business_name, activity_description=activity_description,
            timezone_name=timezone_name,
        )
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ValueError("business_settings_expected_revision_invalid")
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key.strip()) <= 200:
            raise ValueError("business_settings_idempotency_key_required")
        key = idempotency_key.strip()
        fingerprint = sha256(
            json.dumps([name, activity, timezone], separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        with _intake_lock(self._storage_path):
            if not self._storage_path.exists():
                raise KeyError("business_settings_not_found")
            row = _latest_business_row(
                self._storage_path.read_text(encoding="utf-8").splitlines(),
                tenant_id=tenant, business_id=business,
            )
            old_revision = int(row.get("settings_revision") or 0)
            if row.get("settings_last_key") == key:
                if row.get("settings_last_fingerprint") != fingerprint:
                    raise ValueError("business_settings_idempotency_conflict")
                return _settings_payload(row)
            if old_revision != expected_revision:
                raise RuntimeError("business_settings_stale_revision")
            profile = dict(row.get("business_profile") or {})
            profile["name"] = name
            first_value = dict(row.get("first_value_preview") or {})
            first_value["business_name"] = name
            original_payload = dict(row.get("payload") or {})
            original_payload["business_name"] = name
            next_row = {
                **row,
                "business_profile": profile,
                "payload": original_payload,
                "first_value_preview": first_value,
                "business_settings": {"activity_description": activity, "timezone_name": timezone},
                "settings_revision": old_revision + 1,
                "settings_last_key": key,
                "settings_last_fingerprint": fingerprint,
                "settings_actor_id": str(actor_id or "").strip(),
                "settings_updated_at": datetime.now(UTC).isoformat(),
            }
            _append_intake_row(self._storage_path, next_row)
            return _settings_payload(next_row)


def _row_owner_account_id(row: dict[str, object]) -> str:
    explicit = str(row.get("owner_account_id") or "").strip()
    return explicit or _stable_id("owner", str(row.get("user_id") or ""))


def _status_from_row(token: str, row: dict[str, object]) -> CTAIntakeStatus:
    payload = dict(row.get("payload") or {}) if isinstance(row.get("payload"), dict) else {}
    profile = dict(row.get("business_profile") or {}) if isinstance(row.get("business_profile"), dict) else _business_profile(payload)
    selected = tuple(str(x) for x in row.get("selected_providers", ()) if str(x).strip()) if isinstance(row.get("selected_providers"), list) else _selected_providers(payload)
    autonomy = str(row.get("autonomy_mode") or _autonomy_mode(payload))
    plan = tuple(x for x in row.get("integration_plan", ()) if isinstance(x, dict)) if isinstance(row.get("integration_plan"), list) else _integration_plan(selected)
    return CTAIntakeStatus(
        intake_id=token, found=True, outcome=str(row.get("outcome") or "intake_recorded"), created_at=str(row.get("created_at") or ""),
        tenant_id=str(row.get("tenant_id") or ""), business_id=str(row.get("business_id") or ""), user_id=str(row.get("user_id") or ""),
        owner_account_id=_row_owner_account_id(row), onboarding_status=str(row.get("onboarding_status") or "advisory_intake_created"),
        next_actions=tuple(x for x in row.get("next_actions", ()) if isinstance(x, dict)),
        user_functionality=dict(row.get("user_functionality") or {}) or None, admin_visibility=dict(row.get("admin_visibility") or {}) or None, business_profile=profile,
        selected_providers=selected, integration_plan=plan, autonomy_mode=autonomy, first_value_preview=dict(row.get("first_value_preview") or _first_value(profile, selected)),
        onboarding_progress=dict(row.get("onboarding_progress") or _progress(profile, selected, autonomy)),
    )


def _admin_row(row: dict[str, object]) -> dict[str, object]:
    payload = dict(row.get("payload") or {}) if isinstance(row.get("payload"), dict) else {}
    profile = dict(row.get("business_profile") or {}) if isinstance(row.get("business_profile"), dict) else _business_profile(payload)
    return {
        "intake_id": str(row.get("intake_id") or ""), "created_at": str(row.get("created_at") or ""),
        "tenant_id": str(row.get("tenant_id") or ""), "business_id": str(row.get("business_id") or ""),
        "user_id": str(row.get("user_id") or ""), "owner_account_id": _row_owner_account_id(row), "business_name": str(profile.get("name") or ""),
        "industry": str(profile.get("industry") or ""), "city": str(profile.get("city") or ""),
        "outcome": str(row.get("outcome") or ""), "onboarding_status": str(row.get("onboarding_status") or ""),
        "selected_providers": list(row.get("selected_providers") or ()), "autonomy_mode": str(row.get("autonomy_mode") or "advisor"),
        "admin_visibility": dict(row.get("admin_visibility") or {}), "read_only": True,
    }


def _first(payload: dict[str, object], *keys: str) -> str:
    return next((str(payload[key]).strip() for key in keys if payload.get(key) is not None and str(payload[key]).strip()), "")


def _stable_id(prefix: str, value: str) -> str:
    cleaned = "-".join(filter(None, "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value).strip()).split("-")))
    return f"{prefix}-{cleaned[:48]}" if cleaned else f"{prefix}-unknown"


def _business_profile(payload: dict[str, object]) -> dict[str, object]:
    name, email, industry = _first(payload, "business_name", "company"), _first(payload, "email"), _first(payload, "industry", "business_type")
    return {"name": name, "email": email, "contact_email": email, "website": _first(payload, "website", "channel"),
            "industry": industry, "city": _first(payload, "city", "location"), "business_model": _first(payload, "business_model"),
            "goal": _first(payload, "goal", "intent") or "growth", "profile_complete": bool(name and industry)}


def _selected_providers(payload: dict[str, object]) -> tuple[str, ...]:
    raw, known, selected = payload.get("selected_providers"), provider_map(), []
    if not isinstance(raw, list | tuple):
        return ()
    for item in raw:
        key = str(item or "").strip()
        if key and key in known and key not in selected:
            selected.append(key)
        if len(selected) == 32:
            break
    return tuple(selected)


def _autonomy_mode(payload: dict[str, object]) -> str:
    value = {"adviser": "advisor", "helper": "assistant"}.get(str(payload.get("autonomy_mode") or "advisor").strip().lower(), str(payload.get("autonomy_mode") or "advisor").strip().lower())
    return value if value in _AUTONOMY_LABELS else "advisor"


def _integration_plan(selected: tuple[str, ...]) -> tuple[dict[str, object], ...]:
    market = {row["provider_key"]: row for row in public_integration_marketplace()}
    return tuple({"provider_key": key, "title": market[key]["title"], "category": market[key]["category"],
                  "status": "credentials_required" if market[key]["selectable"] else "not_available", "read_only": True,
                  "write_actions_enabled": False, "credential_labels": list(market[key]["credential_labels"]),
                  "next_step": "authenticate_and_verify" if market[key]["selectable"] else "wait_for_provider_readiness"}
                 for key in selected if key in market)


def _first_value(profile: dict[str, object], selected: tuple[str, ...]) -> dict[str, object]:
    checks = _GOAL_CHECKS.get(str(profile.get("goal") or "growth"), _GOAL_CHECKS["growth"])
    return {"kind": "post_sync_preview", "title": "Первый полезный результат",
            "message": "После первого read-only sync система покажет конкретные точки потерь и роста на ваших данных.",
            "checks": list(checks), "selected_data_sources": list(selected), "requires_real_sync": True,
            "contains_estimated_financial_claims": False, "business_name": str(profile.get("name") or "")}


def _progress(profile: dict[str, object], selected: tuple[str, ...], autonomy: str) -> dict[str, object]:
    steps = (("business_profile", bool(profile.get("name") or profile.get("website") or profile.get("email"))),
             ("goal_selected", bool(profile.get("goal"))), ("integrations_selected", bool(selected)),
             ("autonomy_mode_selected", autonomy in _AUTONOMY_LABELS), ("credentials_verified", False), ("first_sync_completed", False))
    done = sum(flag for _, flag in steps)
    return {"completed": done, "total": len(steps), "percent": round(done / len(steps) * 100),
            "steps": [{"code": code, "done": flag} for code, flag in steps]}


def _next_actions(intake_id: str, tenant_id: str, business_id: str, selected: tuple[str, ...]) -> tuple[dict[str, object], ...]:
    return ({"code": "open_app_onboarding", "label": "Открыть кабинет бизнеса", "href": f"/?intake_id={intake_id}", "read_only": True},
            {"code": "connect_data_sources", "label": f"Подключить выбранные источники ({len(selected)})" if selected else "Выбрать источники данных",
             "provider_lifecycle_stage": "selected", "requires_credentials": bool(selected), "write_actions_enabled": False},
            {"code": "review_operator_summary", "label": "Проверить план перед включением внешних действий",
             "tenant_id": tenant_id, "business_id": business_id, "requires_operator": True})


def _user_functionality(intake_id: str, tenant_id: str, business_id: str, user_id: str, autonomy: str, selected: tuple[str, ...]) -> dict[str, object]:
    return {"kind": "businessaios_business_workspace", "intake_id": intake_id, "tenant_id": tenant_id, "business_id": business_id,
            "user_id": user_id, "status": "advisory_intake_created", "autonomy_mode": autonomy,
            "autonomy_mode_label": _AUTONOMY_LABELS[autonomy], "selected_providers": list(selected),
            "available_now": ("business_profile", "integration_marketplace", "connector_selection_plan", "first_value_preview", "operator_review_queue"),
            "blocked_until_approval": ("ad_spend", "customer_messages", "external_publications", "provider_write_actions"),
            "canonical_flow": "business_profile -> integration_selection -> credential_verification -> read_only_sync -> first_value -> approval_gated_execution"}


def _admin_visibility(intake_id: str, tenant_id: str, business_id: str, user_id: str) -> dict[str, object]:
    return {"surface": "control_plane.public_site_cta_intakes", "intake_id": intake_id, "tenant_id": tenant_id,
            "business_id": business_id, "user_id": user_id, "status": "advisory_intake_created", "risk": "low_read_only_onboarding",
            "operator_action": "verify_credentials_then_run_read_only_sync", "write_actions_enabled": False}


__all__ = ["CANON_PUBLIC_SITE_CTA_INTAKE", "CANON_PUBLIC_SITE_INTEGRATION_MARKETPLACE", "CANON_PUBLIC_SITE_USER_ONBOARDING_VIEW",
           "CTAIntakeStatus", "CTALandingIntakeService", "CTASubmitResult", "public_integration_marketplace"]
