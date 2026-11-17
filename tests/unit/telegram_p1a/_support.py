"""Shared fixtures for the P0 Telegram end-to-end contract tests.

``decide`` reproduces what DecisionCore does to a policy proposal before
signing (identity binding + closed-schema validation), so a test that passes
here proves the proposal is executable, not merely well-formed.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from application.decision_runtime.envelope_builder import bind_product_metadata
from core.actions.catalog import build_schema_registry
from core.ai.world_state import WorldStateV1
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import normalize_proposed_action

TENANT, PRODUCT, BUSINESS = "tenant-p0", "organization_platform", "biz-p0"


def write_catalog(root, *, tenant=TENANT, product=PRODUCT, plans=None):
    path = root / "data" / "plan_catalogs" / tenant / f"{product}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"tenant_id": tenant, "product_id": product, "plans": plans or [
        {"plan_id": 2, "title": "Business Workspace", "scope": "monthly", "days": 30,
         "price": 2490, "plan_code": "workspace_month", "is_active": True},
    ]}), encoding="utf-8")
    return path


def make_ctx(*, user_id="1001", text="", cmd=None, args="", callback_data="", callback_query_id=None,
             settings=None, is_admin=False, roles=None, perms=None, admin_metrics=None, tenant=TENANT,
             product=None, full_access=False, selected_tariff=None, pricing_suggestions=None,
             pay_status="none", session=None, meta=None, timestamp_ms=1_700_000_000_000):
    state = WorldStateV1(
        schema_version=1, user={}, session=dict(session or {"channel": "telegram", "source": "messaging"}),
        product=dict({"product_id": PRODUCT, "business_id": BUSINESS} if product is None else product),
        economy={}, timestamp_ms=timestamp_ms, tenant_id=tenant, user_id=str(user_id), meta=dict(meta or {}),
    )
    return TelegramCtx(
        state=state, text=text, cmd=cmd, args=args, callback_data=callback_data,
        callback_query_id=callback_query_id, settings=dict(settings or {}), city="", moods=[],
        admin_metrics=dict(admin_metrics or {}), is_admin=is_admin, roles=list(roles or []),
        perms=list(perms or []), is_superadmin=False, realtime_state={},
        pricing_suggestions=dict(pricing_suggestions or {}), full_access=full_access, pay_status=pay_status,
        selected_tariff=dict(selected_tariff or {}), marketing_variants={}, marketing_seed="1", marketing_bandit={},
    )


def decide(proposal, ctx):
    """DecisionCore binding + closed schema validation; returns the signed-to-be payload."""
    action = normalize_proposed_action(proposal)
    product = ctx.state.product if isinstance(ctx.state.product, dict) else {}
    tagged = bind_product_metadata(
        payload=action.payload, product_id=product.get("product_id"), domain=product.get("domain"),
        product_version=product.get("product_version"), tenant_id=ctx.state.tenant_id, actor_id=ctx.state.user_id,
    )
    payload = dict(tagged.payload)
    business = str(product.get("business_id") or "").strip()
    if business:
        payload["business_id"] = business
    build_schema_registry().validate(action.action, payload)
    return action.action, payload


def env(decision_id="d-1"):
    return SimpleNamespace(decision=SimpleNamespace(decision_id=decision_id, correlation_id=decision_id))
