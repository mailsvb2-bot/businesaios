"""Router -> schema contract for every slash command the Telegram policy knows.

The AST test in ``tests/unit/business_flows/test_policy_payload_schema_guard.py`` only sees literal payload dicts.
This one runs the real router for each command (as admin and as non-admin) and validates the resulting action
payload against the action catalog, the way ``DecisionCore`` would. Known gaps live in an explicit allowlist with a
reason; the allowlist is strict in both directions: a new mismatch fails, and a fixed one must be removed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.actions.catalog import build_schema_registry
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import normalize_proposed_action
from core.policies.telegram.router import handle
from core.policies.telegram.routes.business_flow_routes import BUSINESS_FLOW_COMMANDS

POLICY_DIR = Path(__file__).resolve().parents[2] / "core" / "policies" / "telegram"
_CMD_RE = re.compile(r"""["'](/[a-z][a-z0-9_]{1,40})["']""")

# command -> (outcome, reason). Not product fixes: a real defect is described here and pinned until it is fixed.
KNOWN_ROUTE_GAPS: dict[str, tuple[str, str]] = {
    "/suggest": ("MISSING_REQUIRED_KEYS", "router payload has no business_id; it is expected to be enriched downstream"),
    "/apply_suggest": ("MISSING_REQUIRED_KEYS", "router payload has no business_id; it is expected to be enriched downstream"),
    "/ceo": ("AttributeError", "REAL DEFECT: ai_ceo handler reads ctx.tenant_id / ctx.bot_username which TelegramCtx lacks"),
}


class _State:
    user_id = "u1"
    tenant_id = "t1"
    product = {"product_id": "organization_platform", "domain": "organization_platform"}
    economy: dict = {}


def _ctx(cmd: str, *, is_admin: bool) -> TelegramCtx:
    return TelegramCtx(
        state=_State(), text=cmd, cmd=cmd, args="", callback_data="", callback_query_id=None, settings={},
        city="", moods=[], admin_metrics={}, is_admin=is_admin, roles=[], perms=[], is_superadmin=False,
        realtime_state={}, pricing_suggestions={}, full_access=False, pay_status="none", selected_tariff={},
        marketing_variants={}, marketing_seed="1", marketing_bandit={},
    )


def _all_commands() -> list[str]:
    found = set(BUSINESS_FLOW_COMMANDS)
    for path in POLICY_DIR.rglob("*.py"):
        found |= set(_CMD_RE.findall(path.read_text(encoding="utf-8")))
    return sorted(found)


def _outcome(cmd: str, *, is_admin: bool, extra: dict | None = None) -> str:
    try:
        act = handle(_ctx(cmd, is_admin=is_admin), default_price_rub=4900)
        if act is None:
            return "NO_ACTION"
        act = normalize_proposed_action(act)
        build_schema_registry().validate(act.action, {"tenant_id": "t1", **(extra or {}), **act.payload})
    except Exception as exc:  # noqa: BLE001 - the outcome class is the assertion
        return type(exc).__name__ if not isinstance(exc, ValueError) else str(exc)
    return "OK"


def test_command_universe_is_not_silently_shrinking() -> None:
    cmds = _all_commands()
    assert len(cmds) >= 195 and set(BUSINESS_FLOW_COMMANDS) <= set(cmds)
    assert set(KNOWN_ROUTE_GAPS) <= set(cmds)


@pytest.mark.parametrize("is_admin", [False, True])
def test_every_routed_command_yields_an_action_the_schema_accepts(is_admin) -> None:
    gaps = {}
    for cmd in _all_commands():
        outcome = _outcome(cmd, is_admin=is_admin)
        if outcome != "OK":
            gaps[cmd] = outcome
    assert gaps == {c: o for c, (o, _why) in KNOWN_ROUTE_GAPS.items()}


@pytest.mark.parametrize("cmd", [c for c, (o, _w) in KNOWN_ROUTE_GAPS.items() if o == "MISSING_REQUIRED_KEYS"])
def test_enrichment_only_gaps_are_valid_once_business_id_is_present(cmd) -> None:
    """The allowlisted gap is exactly the missing business_id, nothing else is hidden behind it."""
    for is_admin in (False, True):
        assert _outcome(cmd, is_admin=is_admin, extra={"business_id": "b1"}) == "OK"
