"""Policy payload keys must be accepted by the action catalog schema (B1 regression + guard).

``DecisionCore`` validates every proposed payload against ``core/actions/catalog_groups.py``
(``UNKNOWN_PAYLOAD_KEYS``); a router key the schema does not know silently drops the user's reply.
"""

from __future__ import annotations

import ast
from pathlib import Path

from core.actions.catalog import build_catalog, build_schema_registry
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import normalize_proposed_action
from core.policies.telegram.router import handle
from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline

ROOT = Path(__file__).resolve().parents[3]
SCAN_DIRS = ("core", "application", "runtime", "interfaces")


class _State:
    user_id = "u1"
    tenant_id = "t1"
    product = {"product_id": "organization_platform", "domain": "organization_platform"}


def _ctx(text: str, *, is_admin: bool = False, full_access: bool = False) -> TelegramCtx:
    return TelegramCtx(
        state=_State(), text=text, cmd=None, args="", callback_data="", callback_query_id=None, settings={},
        city="", moods=[], admin_metrics={}, is_admin=is_admin, roles=[], perms=[], is_superadmin=False,
        realtime_state={}, pricing_suggestions={}, full_access=full_access, pay_status="none", selected_tariff={},
        marketing_variants={}, marketing_seed="1", marketing_bandit={},
    )


def test_customer_free_text_router_to_schema_to_handler(flow) -> None:
    """router -> schema validation -> handler: a customer's text gets the policy's reply and a lead fact."""
    for full_access in (False, True):
        act = normalize_proposed_action(handle(_ctx("Хочу записаться на разбор", full_access=full_access), default_price_rub=4900))
        assert act.action == "sales_pipeline@v1"
        payload = {"tenant_id": "t1", **act.payload}
        build_schema_registry().validate(act.action, payload)  # raised UNKNOWN_PAYLOAD_KEYS before the fix
        _out, text = flow.run(handle_sales_pipeline, **act.payload)
        assert text == act.payload["reply"] and text.startswith("Я здесь")
    steps = [e["payload"].get("step") for e in flow.store.events if e["event_type"] == "sales_pipeline@v1"]
    assert "lead_inbound" in steps


def _literal_proposals():
    for d in SCAN_DIRS:
        for path in sorted((ROOT / d).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and len(node.args) > 1 and node.args[0:1]):
                    continue
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                first, second = node.args[0], node.args[1]
                if (
                    name in {"propose", "ProposedAction"}
                    and isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                    and "@v" in first.value
                    and isinstance(second, ast.Dict)
                ):
                    keys = [k.value for k in second.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
                    yield path.relative_to(ROOT).as_posix(), first.value, keys


# Pre-existing mismatches (unchanged files, same on main): out of scope of the B1 fix, pinned so only NEW ones fail.
KNOWN_UNKNOWN_KEYS = {
    ("core/policies/telegram/routes/marketing_routes.py", "select_tariff@v1"): {"notify"},
    ("core/policies/telegram/handlers/admin_pricing.py", "apply_pricing_change@v1"): {"plan_id", "requested_by", "notify_text", "notify_reply_markup"},
    ("core/policies/telegram/handlers/admin_pricing.py", "request_pricing_change@v1"): {"plan_id", "notify_text", "notify_reply_markup"},
    ("core/policies/telegram/handlers/admin/pricing.py", "request_pricing_change@v1"): {"requested_by", "plan_id", "note", "callback_query_id", "notify_text", "notify_reply_markup"},
    ("core/policies/telegram/handlers/admin/pricing.py", "reject_pricing_change@v1"): {"notify_text", "notify_reply_markup", "callback_query_id"},
    ("core/policies/telegram/handlers/ai_ceo.py", "ai_ceo_plan@v1"): {"text", "reply_markup", "callback_query_id", "track_event_type", "track_payload"},
    ("core/policies/telegram/handlers/ai_ceo.py", "execute_plan@v1"): {"callback_query_id"},
}


def _unknown_keys(action: str, keys: list[str]) -> set[str]:
    schema = build_catalog()[action].schema
    base = {k: "x" for k in schema.required}
    unknown = set()
    for key in keys:
        try:
            schema.validate({**base, key: "x"})
        except ValueError as exc:
            if str(exc) == "UNKNOWN_PAYLOAD_KEYS":
                unknown.add(key)
    return unknown


def test_literal_policy_payload_keys_are_known_to_the_catalog_schema() -> None:
    proposals = list(_literal_proposals())
    assert len(proposals) > 30  # the scan really sees the policies
    found: dict[tuple[str, str], set[str]] = {}
    for path, action, keys in proposals:
        assert action in build_catalog(), f"{path}: unknown action {action}"
        unknown = _unknown_keys(action, keys)
        if unknown:
            found.setdefault((path, action), set()).update(unknown)
    new = {k: v - KNOWN_UNKNOWN_KEYS.get(k, set()) for k, v in found.items()}
    assert not {k: sorted(v) for k, v in new.items() if v}, "payload keys missing in core/actions/catalog_groups.py"
