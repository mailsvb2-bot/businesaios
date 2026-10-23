"""Telegram commands for event-sourced business flows -> DecisionCore actions.

One table, no logic: each command proposes exactly one action with an ``op``.
Owner-only commands require ``ctx.is_admin``.
"""

from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose

# cmd -> (action, op, owner_only)
BUSINESS_FLOW_COMMANDS: dict[str, tuple[str, str, bool]] = {
    "/connect_bot": ("bot_provisioning@v1", "request", True),
    "/bot_status": ("bot_provisioning@v1", "status", True),
    "/cancel_bot": ("bot_provisioning@v1", "cancel", True),
    "/add_slot": ("bookings@v1", "add_slot", True),
    "/slots": ("bookings@v1", "list", False),
    "/book": ("bookings@v1", "book", False),
    "/my_bookings": ("bookings@v1", "mine", False),
    "/cancel_booking": ("bookings@v1", "cancel", False),
    "/me": ("bookings@v1", "home", False),
    "/delete_my_data": ("privacy_delete@v1", "request", False),
    "/partner_add": ("partners@v1", "add", True),
    "/partners": ("partners@v1", "rank", True),
    "/ladder_add": ("offer_ladder@v1", "add", True),
    "/ladder": ("offer_ladder@v1", "show", True),
    "/ops": ("business_ops_summary@v1", "show", True),
    "/cockpit": ("business_ops_summary@v1", "cockpit", True),
    "/send_reminders": ("bookings@v1", "dispatch", True),
    "/promote": ("bookings@v1", "promote", True),
    "/add_sessions": ("bookings@v1", "add_sessions", True),
    "/edit_slot": ("bookings@v1", "edit_slot", True),
    "/reschedule_slot": ("bookings@v1", "reschedule_slot", True),
    "/schedule": ("bookings@v1", "schedule", True),
    "/link_channels": ("bookings@v1", "link_channels", False),
    "/announce": ("bookings@v1", "announce", True),
    "/event_promo": ("bookings@v1", "event_promo", True),
    "/attention": ("bookings@v1", "attention", True),
    "/ad_channels": ("bookings@v1", "ad_channels", True),
    "/ad_channel": ("bookings@v1", "ad_channel", True),
    "/setup_channel": ("bookings@v1", "setup_channel", True),
    "/journey": ("bookings@v1", "journey", True),
    "/promotions": ("bookings@v1", "promotions", True),
    "/promo_book": ("bookings@v1", "promo_book", False),
    "/bot_secret": ("bot_provisioning@v1", "attach", True),
    "/verify_bot": ("bot_provisioning@v1", "verify", True),
    "/partner_status": ("partners@v1", "status", True),
    "/partner_pitch": ("partners@v1", "pitch", True),
    "/partner_ref": ("partners@v1", "ref", True),
    "/setting": ("business_admin@v1", "setting", True),
    "/autopilot": ("business_admin@v1", "autopilot", True),
    "/price": ("business_admin@v1", "price", True),
    "/pay": ("business_admin@v1", "pay", True),
    "/refund": ("business_admin@v1", "refund", True),
    "/payments": ("business_admin@v1", "summary", True),
    "/approvals": ("business_admin@v1", "approvals", True),
    "/posts": ("business_admin@v1", "posts", True),
    "/audit": ("business_admin@v1", "audit", True),
    "/post_add": ("business_admin@v1", "post_add", True),
    "/post_schedule": ("business_admin@v1", "post_schedule", True),
    "/post_unschedule": ("business_admin@v1", "post_unschedule", True),
    "/post_publish": ("business_admin@v1", "post_publish", True),
    "/post_retire": ("business_admin@v1", "post_retire", True),
    "/approve": ("business_admin@v1", "approve", True),
    "/reject": ("business_admin@v1", "reject", True),
    "/revoke": ("business_admin@v1", "revoke", True),
    "/series": ("event_series@v1", "preview", True),
    "/series_text": ("event_series@v1", "text", True),
    "/series_reset": ("event_series@v1", "reset", True),
    "/warmup_days": ("event_series@v1", "warmup_days", True),
    "/attendance": ("event_series@v1", "attendance", True),
    "/send_series": ("event_series@v1", "dispatch", True),
    "/offers_on": ("event_series@v1", "offers_on", False),
    "/offers_off": ("event_series@v1", "offers_off", False),
    "/new_event": ("event_series@v1", "wizard_start", True),
    "/event_place": ("event_series@v1", "place", True),
    "/followups": ("event_series@v1", "followups", True),
    "/landing": ("event_series@v1", "landing", True),
    "/visual": ("event_series@v1", "visual", True),
    "/invites": ("business_admin@v1", "invites", True),
    "/invite_new": ("business_admin@v1", "invite_new", True),
    "/join": ("business_admin@v1", "join", False),
    "/policy": ("business_admin@v1", "policy", True),
    "/policy_draft": ("business_admin@v1", "policy_draft", True),
    "/policy_approve": ("business_admin@v1", "policy_approve", True),
    "/policy_revoke": ("business_admin@v1", "policy_revoke", True),
    "/policy_check": ("business_admin@v1", "policy_check", True),
    "/ads": ("business_admin@v1", "ad_list", True),
    "/ad_draft": ("business_admin@v1", "ad_draft", True),
    "/ad_consent": ("business_admin@v1", "ad_consent", True),
    "/directions": ("business_admin@v1", "directions", True),
    "/direction": ("business_admin@v1", "direction", True),
    "/direction_add": ("business_admin@v1", "direction_add", True),
    "/direction_edit": ("business_admin@v1", "direction_edit", True),
    "/direction_goal": ("business_admin@v1", "direction_goal", True),
    "/direction_archive": ("business_admin@v1", "direction_archive", True),
    "/direction_restore": ("business_admin@v1", "direction_restore", True),
    "/offerings": ("business_admin@v1", "offerings", True),
    "/offering_add": ("business_admin@v1", "offering_add", True),
    "/offering_retire": ("business_admin@v1", "offering_retire", True),
    "/formats": ("business_admin@v1", "formats", True),
    "/format_on": ("business_admin@v1", "format_on", True),
    "/format_off": ("business_admin@v1", "format_off", True),
    "/profile": ("business_admin@v1", "profile", True),
    "/profile_set": ("business_admin@v1", "profile_set", True),
    "/ad_stats": ("business_admin@v1", "ad_stats", True),
    "/ad_report": ("business_admin@v1", "ad_report", True),
    "/ad_publish": ("business_admin@v1", "ad_publish", True),
    "/xp": ("business_admin@v1", "xp_list", True),
    "/xp_add": ("business_admin@v1", "xp_add", True),
    "/xp_activate": ("business_admin@v1", "xp_activate", True),
    "/xp_bind": ("business_admin@v1", "xp_bind", True),
    "/xp_disable": ("business_admin@v1", "xp_disable", True),
    "/xp_feedback": ("business_admin@v1", "xp_feedback", True),
    "/xp_value": ("business_admin@v1", "xp_value", True),
    "/leads": ("sales_pipeline@v1", "list", True),
    "/lead_add": ("sales_pipeline@v1", "add", True),
    "/retention": ("sales_pipeline@v1", "retention", True),
    "/reactivate": ("sales_pipeline@v1", "reactivate", True),
    "/lead": ("sales_pipeline@v1", "event", True),
    "/lead_reopen": ("sales_pipeline@v1", "reopen", True),
    "/lead_next": ("sales_pipeline@v1", "next", True),
    "/lead_note": ("sales_pipeline@v1", "note", True),
    "/lead_ai": ("sales_pipeline@v1", "ai", True),
    "/lead_card": ("sales_pipeline@v1", "card", True),
    "/leads_due": ("sales_pipeline@v1", "due", True),
    "/lead_followups": ("sales_pipeline@v1", "followup", True),
    "/lead_followup": ("sales_pipeline@v1", "followup_plan", True),
    "/lead_followup_cancel": ("sales_pipeline@v1", "followup_cancel", True),
    "/lead_optout": ("sales_pipeline@v1", "optout", True),
    "/send_followups": ("sales_pipeline@v1", "followup_dispatch", True),
}


def handle_business_flow_routes(ctx: TelegramCtx, *, user_id: str) -> ProposedAction | None:
    session = getattr(getattr(ctx, "state", None), "session", None) or {}
    if session.get("source") == "external_product_webhook":  # pre-authenticated HTTP ingress
        return propose("business_admin@v1", {"user_id": user_id, "op": "xp_ingest", "arg": "",
                                             "connector_id": str(session.get("connector_id") or "")[:64],
                                             "raw_body": str(session.get("raw_body") or "")[:65536],
                                             "headers": dict(session.get("headers") or {})})  # fmt: skip
    data = str(getattr(ctx, "callback_data", "") or "")
    cbq = str(getattr(ctx, "callback_query_id", "") or "").strip()
    ack = {"callback_query_id": cbq} if cbq else {}  # stop the Telegram button spinner
    if data.startswith("cpm:") and ctx.is_admin:
        return propose("business_ops_summary@v1", {"user_id": user_id, "op": "cockpit", "arg": data[:120], **ack})
    if data.startswith("cpe:") and ctx.is_admin:
        return propose("event_series@v1", {"user_id": user_id, "op": "wizard", "arg": data[:64], **ack})
    args = str(ctx.args or "").strip()
    if ctx.cmd == "/start" and args.startswith("cpa_"):  # promotion deep link -> verified opened touch
        return propose("bookings@v1", {"user_id": user_id, "op": "promo_open", "arg": args[:64]})
    if ctx.cmd == "/start" and args.startswith("ecv_"):  # booking messenger verification link
        return propose("bookings@v1", {"user_id": user_id, "op": "channel_verify", "arg": args[:200]})
    route = BUSINESS_FLOW_COMMANDS.get(str(ctx.cmd or ""))
    if route is None:
        return None
    action, op, owner_only = route
    if op == "home" and ctx.is_admin:
        op = "home_owner"  # owner /me also shows the client journey
    if owner_only and not ctx.is_admin:
        return None
    return propose(action, {"user_id": user_id, "op": op, "arg": str(ctx.args or "").strip()[:200]})


__all__ = ["BUSINESS_FLOW_COMMANDS", "handle_business_flow_routes"]
