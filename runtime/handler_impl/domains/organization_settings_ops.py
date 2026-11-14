"""Telegram organization card backed exclusively by OrganizationRegistry."""
from __future__ import annotations

from application.organization.registry import OrganizationRegistry
from contracts.organization import OrganizationStatus


def organization_card(*, registry: OrganizationRegistry, tenant_id: str, business_id: str,
                      user_id: str, operation: str, arg: str, decision_id: str) -> tuple[str, dict]:
    if operation not in {"organization_show", "organization_create", "organization_name", "organization_type"}:
        raise ValueError("unsupported_organization_operation")
    organizations = registry.list_for_business(tenant_id=tenant_id, business_id=business_id)
    active = [item for item in organizations if item.status is OrganizationStatus.ACTIVE]
    preferred = next((item for item in active if item.organization_id == business_id), None)
    if preferred is None and len(active) == 1:
        preferred = active[0]
    if len(active) > 1 and preferred is None:
        raise ValueError("multiple_organizations_require_explicit_selection")
    if operation != "organization_show" and not arg:
        raise ValueError("organization_value_required")

    identity = {"tenant_id": tenant_id, "business_id": business_id}
    audit = {"actor_id": user_id, "decision_id": decision_id}
    if operation == "organization_create":
        if preferred is not None:
            raise ValueError("organization_already_exists")
        name, divider, kind = arg.partition("|")
        if not name.strip():
            raise ValueError("organization_name_required")
        preferred = registry.create(
            **identity, organization_id=business_id, idempotency_key=decision_id,
            name=name.strip(), organization_type=kind.strip() if divider else None,
            event_metadata=audit,
        )
    elif operation in {"organization_name", "organization_type"}:
        if preferred is None:
            raise ValueError("organization_not_created")
        value = arg.strip()
        if operation == "organization_name" and preferred.name != value:
            preferred = registry.update(**identity, organization_id=preferred.organization_id,
                                        idempotency_key=decision_id, name=value, event_metadata=audit)
        if operation == "organization_type" and preferred.organization_type != value:
            preferred = registry.update(**identity, organization_id=preferred.organization_id,
                                        idempotency_key=decision_id, organization_type=value, event_metadata=audit)

    # Always read back from the existing registry after a mutation; no UI cache.
    if preferred is not None:
        preferred = registry.get(**identity, organization_id=preferred.organization_id)
        text = (f"🏢 Организация\n\nНазвание: {preferred.name or 'не указано'}\n"
                f"Тип: {preferred.organization_type or 'не указан'}\n"
                f"Статус: {preferred.status.value}\n"
                f"ID: {preferred.organization_id}\n\n"
                "Изменить название: /org_name Новое название\n"
                "Изменить тип: /org_type Новый тип")
    else:
        text = ("🏢 Организация\n\nКарточка ещё не создана.\n"
                "Создать: /org_create Название организации | тип")
    markup = {"inline_keyboard": [
        [{"text": "🔄 Обновить карточку", "callback_data": "cp:settings:organization"}],
        [{"text": "⬅️ Настройки", "callback_data": "settings:menu"}],
    ]}
    return text, markup
