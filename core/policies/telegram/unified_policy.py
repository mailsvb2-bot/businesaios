from __future__ import annotations

from dataclasses import dataclass, replace

from core.policies.product_domains.retention_domain import RetentionDomainPolicyV1
from core.policies.product_domains.sales_domain import SalesDomainPolicyV1
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, normalize_proposed_action
from core.policies.telegram.retention_integration import apply_retention_constraints_to_state
from core.policies.telegram.router import handle
from core.policies.telegram.unified_policy_context import extract_session_fields, extract_user_fields
from core.retention.decision_adapter import RetentionDecisionAdapter
from kernel.world_state import WorldStateV1


@dataclass
class UnifiedTelegramPolicyV3:
    """Primary Telegram policy under the single DecisionCore ranking stage."""

    id: str = "telegram_policy@v3"
    allow_rank_fallback: bool = True

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
        self._admin_user_ids = {
            str(value).strip() for value in admin_user_ids if str(value).strip()
        }
        self._bot_username = str(bot_username or "").strip().lstrip("@")
        try:
            gift_ttl = int(gift_ttl_sec)
        except (TypeError, ValueError):
            gift_ttl = 7 * 24 * 3600
        self._gift_ttl_sec = gift_ttl if gift_ttl > 0 else 7 * 24 * 3600
        self._retention = retention
        self._sales = SalesDomainPolicyV1()
        self._ret = RetentionDomainPolicyV1()

    @staticmethod
    def _domain(state: WorldStateV1) -> str:
        product = getattr(state, "product", None)
        values = product if isinstance(product, dict) else {}
        return str(values.get("domain") or "organization_platform")

    def _domain_proposal(self, state: WorldStateV1) -> ProposedAction | None:
        domain = self._domain(state)
        if domain == "sales":
            return normalize_proposed_action(self._sales.propose(state))
        if domain == "retention":
            return normalize_proposed_action(self._ret.propose(state))
        return None

    def _context(self, state: WorldStateV1) -> tuple[TelegramCtx, bool]:
        session_fields = extract_session_fields(state)
        user_fields = extract_user_fields(state)
        economy = dict(getattr(state, "economy", {}) or {})
        entitlements = economy.get("entitlements")
        entitlements = entitlements if isinstance(entitlements, dict) else {}
        payments = economy.get("payments")
        payments = payments if isinstance(payments, dict) else {}
        roles = [str(role) for role in list(user_fields["roles"]) if str(role).strip()]
        permissions = [
            str(permission)
            for permission in list(user_fields["perms"])
            if str(permission).strip()
        ]
        is_superadmin = bool(state.user_id) and str(state.user_id) in self._admin_user_ids
        is_admin = bool(is_superadmin) or "admin" in set(roles)
        pricing_suggestions: dict[str, int] = {}
        for key, value in dict(user_fields["pricing_suggestions"]).items():
            try:
                if str(key).strip():
                    pricing_suggestions[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        context = TelegramCtx(
            state=state,
            text=str(session_fields["text"]),
            cmd=session_fields["cmd"],
            args=str(session_fields["args"]),
            callback_data=str(session_fields["callback_data"]),
            callback_query_id=session_fields["callback_query_id"],
            settings=dict(user_fields["settings"]),
            city=str(user_fields["city"]),
            moods=list(user_fields["moods"]),
            admin_metrics=dict(user_fields["admin_metrics"]),
            is_admin=is_admin,
            roles=roles,
            perms=permissions,
            is_superadmin=bool(is_superadmin),
            realtime_state=dict(user_fields["realtime_state"]),
            pricing_suggestions=pricing_suggestions,
            full_access=bool(entitlements.get("full_access")),
            pay_status=str(payments.get("status") or "none"),
            selected_tariff=dict(user_fields["selected_tariff"]),
            marketing_variants=dict(user_fields["marketing_variants"]),
            marketing_seed=str(user_fields["marketing_seed"]),
            marketing_bandit=dict(user_fields["marketing_bandit"]),
            autopilot_dashboard=dict(user_fields["autopilot_dashboard"]),
        )
        return context, is_admin

    def _propose_base(self, state: WorldStateV1) -> ProposedAction:
        domain = self._domain_proposal(state)
        if domain is not None:
            return domain
        context, _is_admin = self._context(state)
        return normalize_proposed_action(
            handle(
                context,
                default_price_rub=self._default_price_rub,
                bot_username=self._bot_username,
                gift_ttl_sec=self._gift_ttl_sec,
            )
        )

    def propose(self, state: WorldStateV1) -> ProposedAction:
        """Compatibility: produce the unchanged base UX action."""

        return self._propose_base(state)

    def propose_many(self, state: WorldStateV1) -> list[ProposedAction]:
        """Expose base and retention alternatives to canonical DecisionCore ranking."""

        domain = self._domain_proposal(state)
        if domain is not None:
            return [domain]
        context, is_admin = self._context(state)
        telegram_update = getattr(state, "telegram_update", None)
        if self._retention is None or is_admin or telegram_update is None:
            return [
                normalize_proposed_action(
                    handle(
                        context,
                        default_price_rub=self._default_price_rub,
                        bot_username=self._bot_username,
                        gift_ttl_sec=self._gift_ttl_sec,
                    )
                )
            ]

        evaluation = self._retention.evaluate(state)
        constrained_state = apply_retention_constraints_to_state(
            state=state,
            evaluation=evaluation,
        )
        if constrained_state is not state:
            context = replace(context, state=constrained_state)
        base = normalize_proposed_action(
            handle(
                context,
                default_price_rub=self._default_price_rub,
                bot_username=self._bot_username,
                gift_ttl_sec=self._gift_ttl_sec,
            )
        )
        return self._retention.propose_candidates(
            state=constrained_state,
            base=base,
            evaluation=evaluation,
        )
