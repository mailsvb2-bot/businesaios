from __future__ import annotations

from dataclasses import dataclass, replace

from core.observability.silent import swallow
from core.policies.product_domains.retention_domain import RetentionDomainPolicyV1
from core.policies.product_domains.sales_domain import SalesDomainPolicyV1
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction
from core.policies.telegram.retention_integration import apply_retention_constraints_to_state, merge_retention_plan
from core.policies.telegram.router import handle
from core.policies.telegram.unified_policy_context import extract_session_fields, extract_user_fields
from core.retention.decision_adapter import RetentionDecisionAdapter
from kernel.world_state import WorldStateV1


@dataclass
class UnifiedTelegramPolicyV3:
    """Primary user-facing Telegram policy.

    Keeps *business/UX branching* in one place, but never performs side-effects.
    All side-effects go through DecisionCore -> RuntimeExecutor -> EffectsPort.

    This class is intentionally small; the routing logic lives in telegram/router.py.
    """

    id: str = "telegram_policy" + "@v3"

    def __init__(
        self,
        *,
        pricing_rub: int = 4900,
        admin_user_ids: tuple[str, ...] = (),
        bot_username: str = "",
        gift_ttl_sec: int = 7 * 24 * 3600,
        retention: RetentionDecisionAdapter | None = None,
    ) -> None:
        self._default_price_rub = int(pricing_rub)
        self._admin_user_ids = {str(x).strip() for x in admin_user_ids if str(x).strip()}
        self._bot_username = str(bot_username or "").strip().lstrip("@")
        try:
            g = int(gift_ttl_sec)
        except Exception:
            g = 7 * 24 * 3600
        self._gift_ttl_sec = g if g > 0 else 7 * 24 * 3600
        self._retention = retention

        # Product-domain delegates (keep DecisionCore policy count minimal).
        self._sales = SalesDomainPolicyV1()
        self._ret = RetentionDomainPolicyV1()

    def propose(self, state: WorldStateV1) -> ProposedAction:
        # Engine/product separation: optional domain routing.
        # If state.product.domain is not organization_platform, route inside the unified policy.
        try:
            prod = dict(getattr(state, "product", {}) or {})
            domain = str(prod.get("domain") or "organization_platform")
        except Exception:
            domain = "organization_platform"

        if domain == "sales":
            return self._sales.propose(state)
        if domain == "retention":
            return self._ret.propose(state)

        session_fields = extract_session_fields(state)
        text = str(session_fields["text"])
        cmd = session_fields["cmd"]
        args = str(session_fields["args"])
        cb = str(session_fields["callback_data"])
        callback_query_id = session_fields["callback_query_id"]

        user_fields = extract_user_fields(state)
        settings = dict(user_fields["settings"])
        city = str(user_fields["city"])
        moods = list(user_fields["moods"])
        admin_metrics = dict(user_fields["admin_metrics"])
        selected = dict(user_fields["selected_tariff"])
        marketing_variants = dict(user_fields["marketing_variants"])
        marketing_seed = str(user_fields["marketing_seed"])
        marketing_bandit = dict(user_fields["marketing_bandit"])
        roles = list(user_fields["roles"])
        perms = list(user_fields["perms"])
        realtime_state = dict(user_fields["realtime_state"])
        autopilot_dashboard = dict(user_fields["autopilot_dashboard"])
        pricing_suggestions = dict(user_fields["pricing_suggestions"])

        econ = dict(getattr(state, "economy", {}) or {})
        ent = dict((econ.get("entitlements") or {}) if isinstance(econ.get("entitlements"), dict) else {})
        full = bool(ent.get("full_access"))
        pay = econ.get("payments") if isinstance(econ.get("payments"), dict) else {}
        pay_status = str((pay or {}).get("status") or "none")

        is_superadmin = bool(state.user_id) and str(state.user_id) in self._admin_user_ids
        is_admin = bool(is_superadmin) or ("admin" in {str(r) for r in roles})

        ctx = TelegramCtx(
            state=state,
            text=text,
            cmd=cmd,
            args=args,
            callback_data=cb,
            callback_query_id=callback_query_id,
            settings=settings,
            city=city,
            moods=moods,
            admin_metrics=admin_metrics,
            is_admin=is_admin,
            roles=[str(r) for r in roles if str(r).strip()],
            perms=[str(p) for p in perms if str(p).strip()],
            is_superadmin=bool(is_superadmin),
            realtime_state=realtime_state,
            pricing_suggestions={str(k): int(v) for k, v in pricing_suggestions.items() if str(k).strip()},
            full_access=full,
            pay_status=pay_status,
            selected_tariff=selected,
            marketing_variants=marketing_variants,
            marketing_seed=marketing_seed,
            marketing_bandit=marketing_bandit,
            autopilot_dashboard=autopilot_dashboard,
        )
        # Retention must actually affect UX/offers/prices.
        # Strictly additive + deterministic: compute optional retention plan once.
        plan = None
        if self._retention is not None and (not is_admin) and getattr(state, "telegram_update", None) is not None:
            try:
                plan = self._retention.compute_plan(state)
            except Exception:
                plan = None

            # If retention produced deterministic price constraints, merge them into WorldState now
            # so downstream offer renderers can respect DecisionCore constraints.
            try:
                state = apply_retention_constraints_to_state(state=state, plan=plan)
                ctx = replace(ctx, state=state)
            except Exception:
                swallow(__name__, "core/policies/telegram/unified_policy.py")

        base = handle(ctx, default_price_rub=self._default_price_rub)
        return merge_retention_plan(base=base, plan=plan, user_id=str(state.user_id))
