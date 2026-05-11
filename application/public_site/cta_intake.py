from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

CANON_PUBLIC_SITE_CTA_INTAKE = True
CANON_PUBLIC_SITE_USER_ONBOARDING_VIEW = True


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
        created_at = datetime.now(timezone.utc).isoformat()
        tenant_id = _stable_id(prefix="tenant", value=_first_non_empty(safe_payload, "tenant_id", "business_name", "company", "email") or intake_id)
        business_id = _stable_id(prefix="business", value=_first_non_empty(safe_payload, "business_id", "business_name", "company", "website", "email") or intake_id)
        user_id = _stable_id(prefix="user", value=_first_non_empty(safe_payload, "user_id", "email", "telegram", "phone") or intake_id)
        onboarding_status = "advisory_intake_created"
        next_actions = _next_actions(intake_id=intake_id, tenant_id=tenant_id, business_id=business_id)
        user_functionality = _user_functionality(
            intake_id=intake_id,
            tenant_id=tenant_id,
            business_id=business_id,
            user_id=user_id,
            onboarding_status=onboarding_status,
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
            "next_actions": list(next_actions),
            "user_functionality": user_functionality,
            "admin_visibility": admin_visibility,
            "canonical_flow": {
                "stage": "read_only_advisory_onboarding",
                "write_actions_enabled": False,
                "requires_approval_before_execution": True,
                "decision_core_required_for_irreversible_actions": True,
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
        )

    def get_status(self, *, intake_id: str) -> CTAIntakeStatus:
        token = str(intake_id or "").strip()
        if not token or not self._storage_path.exists():
            return CTAIntakeStatus(
                intake_id=token,
                found=False,
                outcome="not_found",
                created_at="",
            )

        for line in self._storage_path.read_text(encoding="utf-8").splitlines()[::-1]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if str(row.get("intake_id") or "") == token:
                return _status_from_row(token=token, row=row)

        return CTAIntakeStatus(
            intake_id=token,
            found=False,
            outcome="not_found",
            created_at="",
        )

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
            if not isinstance(row, dict):
                continue
            rows.append(_admin_row(row))
        return tuple(rows)


def _status_from_row(*, token: str, row: dict[str, object]) -> CTAIntakeStatus:
    next_actions_raw = row.get("next_actions")
    next_actions = tuple(item for item in next_actions_raw if isinstance(item, dict)) if isinstance(next_actions_raw, list) else ()
    user_functionality = row.get("user_functionality") if isinstance(row.get("user_functionality"), dict) else None
    admin_visibility = row.get("admin_visibility") if isinstance(row.get("admin_visibility"), dict) else None
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


def _next_actions(*, intake_id: str, tenant_id: str, business_id: str) -> tuple[dict[str, object], ...]:
    return (
        {
            "code": "open_app_onboarding",
            "label": "Open advisory onboarding workspace",
            "href": f"/?intake_id={intake_id}",
            "read_only": True,
        },
        {
            "code": "connect_data_sources",
            "label": "Connect read-only business data sources",
            "provider_lifecycle_stage": "selected",
            "requires_credentials": True,
            "write_actions_enabled": False,
        },
        {
            "code": "review_operator_summary",
            "label": "Review intake in control-plane before approvals or write actions",
            "tenant_id": tenant_id,
            "business_id": business_id,
            "requires_operator": True,
        },
    )


def _user_functionality(*, intake_id: str, tenant_id: str, business_id: str, user_id: str, onboarding_status: str) -> dict[str, object]:
    return {
        "kind": "businessaios_advisory_workspace",
        "intake_id": intake_id,
        "tenant_id": tenant_id,
        "business_id": business_id,
        "user_id": user_id,
        "status": onboarding_status,
        "available_now": (
            "intake_status",
            "read_only_business_profile",
            "connector_selection_plan",
            "operator_review_queue",
        ),
        "blocked_until_approval": (
            "ad_spend",
            "customer_messages",
            "external_publications",
            "provider_write_actions",
        ),
        "canonical_flow": "landing_cta -> public_api -> advisory_intake -> app_workspace -> operator_review -> approval_gated_execution",
    }


def _admin_visibility(*, intake_id: str, tenant_id: str, business_id: str, user_id: str, onboarding_status: str) -> dict[str, object]:
    return {
        "surface": "control_plane.public_site_cta_intakes",
        "intake_id": intake_id,
        "tenant_id": tenant_id,
        "business_id": business_id,
        "user_id": user_id,
        "status": onboarding_status,
        "risk": "low_read_only_advisory",
        "operator_action": "review_profile_and_request_read_only_connectors",
        "write_actions_enabled": False,
    }


__all__ = [
    "CANON_PUBLIC_SITE_CTA_INTAKE",
    "CANON_PUBLIC_SITE_USER_ONBOARDING_VIEW",
    "CTALandingIntakeService",
    "CTASubmitResult",
    "CTAIntakeStatus",
]
