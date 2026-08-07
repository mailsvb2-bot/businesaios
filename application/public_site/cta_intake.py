from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_truth_matrix import provider_truth_map

CANON_PUBLIC_SITE_CTA_INTAKE = True
CANON_PUBLIC_SITE_USER_ONBOARDING_VIEW = True
CANON_PUBLIC_SITE_INTEGRATION_MARKETPLACE = True

_AUTONOMY_MODES = {
    "advisor": {
        "title": "Советник",
        "description": "Анализирует бизнес и предлагает действия. Ничего не выполняет без человека.",
    },
    "assistant": {
        "title": "Помощник",
        "description": "Автоматизирует безопасные шаги, а важные действия отправляет на подтверждение.",
    },
    "autopilot": {
        "title": "Автопилот",
        "description": "Целевой режим автономной работы в заданных лимитах. Включается только после доказанного подключения и политик безопасности.",
    },
}

_PUBLIC_PROVIDER_ORDER = (
    "telegram_bot",
    "whatsapp_cloud",
    "email_connector",
    "generic_website",
    "wordpress",
    "webflow",
    "shopify",
    "woocommerce",
    "hubspot",
    "ozon_marketplace",
    "wildberries_marketplace",
    "amazon_marketplace",
    "ebay_marketplace",
    "etsy_marketplace",
    "google_ads",
    "meta_ads",
    "tiktok_ads",
    "sms_connector",
    "call_tracking",
)

_RECOMMENDED_PROVIDER_KEYS = {
    "telegram_bot",
    "generic_website",
    "hubspot",
    "ozon_marketplace",
    "wildberries_marketplace",
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
    providers = provider_map()
    truth = provider_truth_map()
    rows: list[dict[str, object]] = []
    for provider_key in _PUBLIC_PROVIDER_ORDER:
        provider = providers.get(provider_key)
        row = truth.get(provider_key)
        if provider is None or row is None:
            continue
        if row.read_only_supported:
            availability = "available_read_only"
            availability_label = "Можно подключить для анализа"
        elif row.status in {"implemented", "partial"}:
            availability = "preparing"
            availability_label = "Подключение готовится"
        else:
            availability = "roadmap"
            availability_label = "Скоро"
        rows.append(
            {
                "provider_key": provider_key,
                "title": provider.title,
                "category": provider.domain,
                "description": provider.description,
                "status": row.status,
                "availability": availability,
                "availability_label": availability_label,
                "selectable": bool(row.read_only_supported),
                "read_supported": bool(row.read_only_supported),
                "write_supported": False,
                "approval_required": bool(row.approval_required),
                "risk_level": row.risk_level,
                "recommended": provider_key in _RECOMMENDED_PROVIDER_KEYS,
                "credential_labels": [field.label for field in provider.secret_fields if field.required],
                "read_capabilities": list(row.read_capabilities),
                "note": "Запись во внешние системы остаётся выключенной до отдельного подтверждения и evidence guard.",
            }
        )
    return tuple(rows)


class CTALandingIntakeService:
    def __init__(
        self,
        *,
        storage_path: str = "runtime_state/pilot_applications.jsonl",
        app_base_url: str = "https://app.businessaios.ru",
    ) -> None:
        self._storage_path = Path(storage_path)
        self._app_base_url = app_base_url.rstrip("/")

    def submit(self, *, payload: dict[str, object]) -> CTASubmitResult:
        safe_payload = dict(payload or {})
        intake_id = f"cta-{uuid4().hex[:16]}"
        created_at = datetime.now(UTC).isoformat()
        business_profile = _business_profile(safe_payload)
        tenant_id = _stable_id(
            prefix="tenant",
            value=_first_non_empty(safe_payload, "tenant_id", "business_name", "company", "email") or intake_id,
        )
        business_id = _stable_id(
            prefix="business",
            value=_first_non_empty(safe_payload, "business_id", "business_name", "company", "website", "email") or intake_id,
        )
        user_id = _stable_id(
            prefix="user",
            value=_first_non_empty(safe_payload, "user_id", "email", "telegram", "phone") or intake_id,
        )
        selected_providers = _selected_providers(safe_payload)
        autonomy_mode = _autonomy_mode(safe_payload)
        integration_plan = _integration_plan(selected_providers)
        first_value_preview = _first_value_preview(
            business_profile=business_profile,
            selected_providers=selected_providers,
            goal=str(safe_payload.get("goal") or safe_payload.get("intent") or "growth"),
        )
        onboarding_status = "integration_plan_ready" if selected_providers else "business_profile_created"
        onboarding_progress = _onboarding_progress(
            business_profile=business_profile,
            selected_providers=selected_providers,
            autonomy_mode=autonomy_mode,
        )
        next_actions = _next_actions(
            intake_id=intake_id,
            tenant_id=tenant_id,
            business_id=business_id,
            selected_providers=selected_providers,
        )
        user_functionality = _user_functionality(
            intake_id=intake_id,
            tenant_id=tenant_id,
            business_id=business_id,
            user_id=user_id,
            onboarding_status=onboarding_status,
            autonomy_mode=autonomy_mode,
            selected_providers=selected_providers,
        )
        admin_visibility = _admin_visibility(
            intake_id=intake_id,
            tenant_id=tenant_id,
            business_id=business_id,
            user_id=user_id,
            onboarding_status=onboarding_status,
        )
        row = {
            "intake_id": intake_id,
            "created_at": created_at,
            "source": "public_landing_cta",
            "payload": safe_payload,
            "outcome": "intake_recorded",
            "tenant_id": tenant_id,
            "business_id": business_id,
            "user_id": user_id,
            "onboarding_status": onboarding_status,
            "business_profile": business_profile,
            "selected_providers": list(selected_providers),
            "integration_plan": list(integration_plan),
            "autonomy_mode": autonomy_mode,
            "first_value_preview": first_value_preview,
            "onboarding_progress": onboarding_progress,
            "next_actions": list(next_actions),
            "user_functionality": user_functionality,
            "admin_visibility": admin_visibility,
            "canonical_flow": {
                "stage": "self_service_read_only_onboarding",
                "write_actions_enabled": False,
                "requires_approval_before_execution": True,
                "decision_core_required_for_irreversible_actions": True,
                "credential_activation_requires_authenticated_control_plane": True,
            },
        }
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return CTASubmitResult(
            intake_id=intake_id,
            created_at=created_at,
            app_url=f"{self._app_base_url}/?intake_id={intake_id}",
            tenant_id=tenant_id,
            business_id=business_id,
            user_id=user_id,
            onboarding_status=onboarding_status,
            next_actions=next_actions,
            user_functionality=user_functionality,
            admin_visibility=admin_visibility,
            business_profile=business_profile,
            selected_providers=selected_providers,
            integration_plan=integration_plan,
            autonomy_mode=autonomy_mode,
            first_value_preview=first_value_preview,
            onboarding_progress=onboarding_progress,
        )

    def get_status(self, *, intake_id: str) -> CTAIntakeStatus:
        token = str(intake_id or "").strip()
        if not token or not self._storage_path.exists():
            return CTAIntakeStatus(intake_id=token, found=False, outcome="not_found", created_at="")

        for line in self._storage_path.read_text(encoding="utf-8").splitlines()[::-1]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if str(row.get("intake_id") or "") == token:
                return _status_from_row(token=token, row=row)

        return CTAIntakeStatus(intake_id=token, found=False, outcome="not_found", created_at="")

    def list_recent(self, *, limit: int = 50) -> tuple[dict[str, object], ...]:
        if not self._storage_path.exists():
            return ()
        rows: list[dict[str, object]] = []
        for line in self._storage_path.read_text(encoding="utf-8").splitlines()[::-1]:
            if len(rows) >= max(1, min(int(limit or 50), 200)):
                break
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(_admin_row(row))
        return tuple(rows)


def _status_from_row(*, token: str, row: dict[str, object]) -> CTAIntakeStatus:
    next_actions_raw = row.get("next_actions")
    next_actions = tuple(item for item in next_actions_raw if isinstance(item, dict)) if isinstance(next_actions_raw, list) else ()
    integration_raw = row.get("integration_plan")
    integration_plan = tuple(item for item in integration_raw if isinstance(item, dict)) if isinstance(integration_raw, list) else ()
    selected_raw = row.get("selected_providers")
    selected_providers = tuple(str(item) for item in selected_raw if str(item).strip()) if isinstance(selected_raw, list) else ()
    user_functionality = row.get("user_functionality") if isinstance(row.get("user_functionality"), dict) else None
    admin_visibility = row.get("admin_visibility") if isinstance(row.get("admin_visibility"), dict) else None
    business_profile = row.get("business_profile") if isinstance(row.get("business_profile"), dict) else None
    first_value_preview = row.get("first_value_preview") if isinstance(row.get("first_value_preview"), dict) else None
    onboarding_progress = row.get("onboarding_progress") if isinstance(row.get("onboarding_progress"), dict) else None
    return CTAIntakeStatus(
        intake_id=token,
        found=True,
        outcome=str(row.get("outcome") or "intake_recorded"),
        created_at=str(row.get("created_at") or ""),
        tenant_id=str(row.get("tenant_id") or ""),
        business_id=str(row.get("business_id") or ""),
        user_id=str(row.get("user_id") or ""),
        onboarding_status=str(row.get("onboarding_status") or "advisory_intake_created"),
        next_actions=next_actions,
        user_functionality=dict(user_functionality) if user_functionality is not None else None,
        admin_visibility=dict(admin_visibility) if admin_visibility is not None else None,
        business_profile=dict(business_profile) if business_profile is not None else None,
        selected_providers=selected_providers,
        integration_plan=integration_plan,
        autonomy_mode=str(row.get("autonomy_mode") or "advisor"),
        first_value_preview=dict(first_value_preview) if first_value_preview is not None else None,
        onboarding_progress=dict(onboarding_progress) if onboarding_progress is not None else None,
    )


def _admin_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "intake_id": str(row.get("intake_id") or ""),
        "created_at": str(row.get("created_at") or ""),
        "tenant_id": str(row.get("tenant_id") or ""),
        "business_id": str(row.get("business_id") or ""),
        "user_id": str(row.get("user_id") or ""),
        "outcome": str(row.get("outcome") or ""),
        "onboarding_status": str(row.get("onboarding_status") or ""),
        "selected_providers": list(row.get("selected_providers") or []),
        "autonomy_mode": str(row.get("autonomy_mode") or "advisor"),
        "admin_visibility": dict(row.get("admin_visibility") or {}) if isinstance(row.get("admin_visibility"), dict) else {},
        "read_only": True,
    }


def _first_non_empty(payload: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _stable_id(*, prefix: str, value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return f"{prefix}-{cleaned[:48]}" if cleaned else f"{prefix}-unknown"


def _business_profile(payload: dict[str, object]) -> dict[str, object]:
    return {
        "name": _first_non_empty(payload, "business_name", "company"),
        "email": _first_non_empty(payload, "email"),
        "website": _first_non_empty(payload, "website"),
        "industry": _first_non_empty(payload, "industry"),
        "city": _first_non_empty(payload, "city"),
        "business_model": _first_non_empty(payload, "business_model"),
        "goal": _first_non_empty(payload, "goal", "intent") or "growth",
    }


def _selected_providers(payload: dict[str, object]) -> tuple[str, ...]:
    raw = payload.get("selected_providers")
    if not isinstance(raw, (list, tuple)):
        return ()
    known = provider_map()
    seen: set[str] = set()
    selected: list[str] = []
    for item in raw:
        key = str(item or "").strip()
        if not key or key in seen or key not in known:
            continue
        seen.add(key)
        selected.append(key)
        if len(selected) >= 12:
            break
    return tuple(selected)


def _autonomy_mode(payload: dict[str, object]) -> str:
    value = str(payload.get("autonomy_mode") or "advisor").strip().lower()
    value = {"adviser": "advisor", "helper": "assistant"}.get(value, value)
    return value if value in _AUTONOMY_MODES else "advisor"


def _integration_plan(selected_providers: tuple[str, ...]) -> tuple[dict[str, object], ...]:
    marketplace = {str(row["provider_key"]): row for row in public_integration_marketplace()}
    plan: list[dict[str, object]] = []
    for key in selected_providers:
        row = marketplace.get(key)
        if row is None:
            continue
        plan.append(
            {
                "provider_key": key,
                "title": row["title"],
                "category": row["category"],
                "status": "credentials_required" if row["selectable"] else "not_available",
                "read_only": True,
                "write_actions_enabled": False,
                "credential_labels": list(row["credential_labels"]),
                "next_step": "authenticate_and_verify" if row["selectable"] else "wait_for_provider_readiness",
            }
        )
    return tuple(plan)


def _first_value_preview(
    *,
    business_profile: dict[str, object],
    selected_providers: tuple[str, ...],
    goal: str,
) -> dict[str, object]:
    normalized_goal = str(goal or "growth").strip().lower()
    checks_by_goal = {
        "growth": ("потерянные лиды", "каналы с лучшей конверсией", "точки роста повторных продаж"),
        "retention": ("клиенты без повторной покупки", "незавершённые диалоги", "сегменты для реактивации"),
        "ads_efficiency": ("кампании с неэффективным расходом", "стоимость привлечения", "расхождения атрибуции"),
        "operations": ("ручные повторяющиеся операции", "очереди без владельца", "задержки исполнения"),
        "sales": ("зависшие сделки", "пропущенные follow-up", "воронка по источникам"),
    }
    checks = checks_by_goal.get(normalized_goal, checks_by_goal["growth"])
    return {
        "kind": "post_sync_preview",
        "title": "Первый полезный результат",
        "message": "После первого read-only sync система покажет конкретные точки потерь и роста на ваших данных.",
        "checks": list(checks),
        "selected_data_sources": list(selected_providers),
        "requires_real_sync": True,
        "contains_estimated_financial_claims": False,
        "business_name": str(business_profile.get("name") or ""),
    }


def _onboarding_progress(
    *,
    business_profile: dict[str, object],
    selected_providers: tuple[str, ...],
    autonomy_mode: str,
) -> dict[str, object]:
    steps = (
        ("business_profile", bool(business_profile.get("name") or business_profile.get("website") or business_profile.get("email"))),
        ("goal_selected", bool(business_profile.get("goal"))),
        ("integrations_selected", bool(selected_providers)),
        ("autonomy_mode_selected", autonomy_mode in _AUTONOMY_MODES),
        ("credentials_verified", False),
        ("first_sync_completed", False),
    )
    completed = sum(1 for _, done in steps if done)
    return {
        "completed": completed,
        "total": len(steps),
        "percent": int(round(completed / len(steps) * 100)),
        "steps": [{"code": code, "done": done} for code, done in steps],
    }


def _next_actions(
    *,
    intake_id: str,
    tenant_id: str,
    business_id: str,
    selected_providers: tuple[str, ...] = (),
) -> tuple[dict[str, object], ...]:
    connect_label = (
        f"Подключить выбранные источники ({len(selected_providers)})"
        if selected_providers
        else "Выбрать источники данных"
    )
    return (
        {
            "code": "open_app_onboarding",
            "label": "Открыть кабинет бизнеса",
            "href": f"/?intake_id={intake_id}",
            "read_only": True,
        },
        {
            "code": "connect_data_sources",
            "label": connect_label,
            "provider_lifecycle_stage": "selected",
            "requires_credentials": bool(selected_providers),
            "write_actions_enabled": False,
        },
        {
            "code": "review_operator_summary",
            "label": "Проверить план перед включением внешних действий",
            "tenant_id": tenant_id,
            "business_id": business_id,
            "requires_operator": True,
        },
    )


def _user_functionality(
    *,
    intake_id: str,
    tenant_id: str,
    business_id: str,
    user_id: str,
    onboarding_status: str,
    autonomy_mode: str = "advisor",
    selected_providers: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "kind": "businessaios_business_workspace",
        "intake_id": intake_id,
        "tenant_id": tenant_id,
        "business_id": business_id,
        "user_id": user_id,
        "status": onboarding_status,
        "autonomy_mode": autonomy_mode,
        "autonomy_mode_label": _AUTONOMY_MODES[autonomy_mode]["title"],
        "selected_providers": list(selected_providers),
        "available_now": (
            "business_profile",
            "integration_marketplace",
            "read_only_business_profile",
            "connector_selection_plan",
            "first_value_preview",
            "operator_review_queue",
        ),
        "blocked_until_approval": (
            "ad_spend",
            "customer_messages",
            "external_publications",
            "provider_write_actions",
        ),
        "canonical_flow": "business_profile -> integration_selection -> credential_verification -> read_only_sync -> first_value -> approval_gated_execution",
    }


def _admin_visibility(*, intake_id: str, tenant_id: str, business_id: str, user_id: str, onboarding_status: str) -> dict[str, object]:
    return {
        "surface": "control_plane.public_site_cta_intakes",
        "intake_id": intake_id,
        "tenant_id": tenant_id,
        "business_id": business_id,
        "user_id": user_id,
        "status": onboarding_status,
        "risk": "low_read_only_onboarding",
        "operator_action": "verify_credentials_then_run_read_only_sync",
        "write_actions_enabled": False,
    }


__all__ = [
    "CANON_PUBLIC_SITE_CTA_INTAKE",
    "CANON_PUBLIC_SITE_INTEGRATION_MARKETPLACE",
    "CANON_PUBLIC_SITE_USER_ONBOARDING_VIEW",
    "CTAIntakeStatus",
    "CTALandingIntakeService",
    "CTASubmitResult",
    "public_integration_marketplace",
]
