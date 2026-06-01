from __future__ import annotations

"""Admin + operator handlers.

Thin orchestrator only. Large UI/admin flows live in small modules under
core/policies/telegram/handlers/admin/ to avoid god-modules and hidden logic.
"""

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.handlers.admin.analytics import handle_analytics
from core.policies.telegram.handlers.admin.commands import handle_admin_commands
from core.policies.telegram.handlers.admin.copywriter import handle_copywriter
from core.policies.telegram.handlers.admin.evolution import handle_evolution
from core.policies.telegram.handlers.admin.menu import handle_admin_menu
from core.policies.telegram.handlers.admin.pricing import handle_pricing
from core.policies.telegram.handlers.admin.roles_perms import handle_roles_perms
from core.policies.telegram.helpers import ProposedAction


def _has_perm(ctx: TelegramCtx, perm: str) -> bool:
    if bool(getattr(ctx, "is_superadmin", False)):
        return True
    perms = {str(x) for x in (getattr(ctx, "perms", []) or [])}
    roles = {str(x) for x in (getattr(ctx, "roles", []) or [])}
    return (str(perm) in perms) or ("admin" in roles)


_HANDLERS = (
    lambda ctx, user_id, pm: handle_admin_commands(ctx, pm=pm),
    lambda ctx, user_id, pm: handle_admin_menu(ctx, pm=pm),
    lambda ctx, user_id, pm: handle_roles_perms(ctx, user_id=user_id, pm=pm),
    lambda ctx, user_id, pm: handle_copywriter(ctx, user_id=user_id, has_perm=_has_perm, pm=pm),
    lambda ctx, user_id, pm: handle_evolution(ctx, user_id=user_id, has_perm=_has_perm, pm=pm),
    lambda ctx, user_id, pm: handle_pricing(ctx, pm=pm),
    lambda ctx, user_id, pm: handle_analytics(ctx, user_id=user_id, pm=pm),
)


def handle_admin(ctx: TelegramCtx, *, user_id: str, pm) -> ProposedAction | None:
    for handler in _HANDLERS:
        result = handler(ctx, user_id, pm)
        if result is not None:
            return result
    return None
