"""Telegram commands for event-sourced business flows -> DecisionCore actions.

One table, no logic: each command proposes exactly one action with an ``op``.
Owner-only commands require ``ctx.is_admin``.
"""

from __future__ import annotations

import re

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
    "/outcomes": ("business_ops_summary@v1", "outcomes", True),
    "/attribution": ("business_ops_summary@v1", "trace", True),
    "/economics": ("business_ops_summary@v1", "economics", True),
    "/journey": ("business_ops_summary@v1", "journey", True),
    "/send_reminders": ("bookings@v1", "dispatch", True),
    "/promote": ("bookings@v1", "promote", True),
    "/add_sessions": ("bookings@v1", "add_sessions", True),
    "/edit_slot": ("bookings@v1", "edit_slot", True),
    "/reschedule_slot": ("bookings@v1", "reschedule_slot", True),
    "/event_schedule": ("bookings@v1", "event_schedule", True),
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
    "/bot_disable": ("bot_provisioning@v1", "disable", True),
    "/bot_activate": ("bot_provisioning@v1", "activate", True),
    "/bot_revoke": ("bot_provisioning@v1", "revoke", True),
    "/bot_managed": ("bot_provisioning@v1", "managed_begin", True),
    "/partner_status": ("partners@v1", "status", True),
    "/partner_pitch": ("partners@v1", "pitch", True),
    "/partner_ref": ("partners@v1", "ref", True),
    "/partner_result": ("partners@v1", "ref_result", True),
    "/partner_campaign": ("partners@v1", "campaign", True),
    "/setting": ("business_admin@v1", "setting", True),
    "/customer_archive": ("business_admin@v1", "customer_archive", True),
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
    "/event_create": ("event_series@v1", "pub_create", True),
    "/event_register": ("event_series@v1", "pub_register", False),
    "/event_links": ("event_series@v1", "pub_links", False),
    "/event_live": ("event_series@v1", "pub_live", True),
    "/event_verify": ("event_series@v1", "pub_verify", False),
    "/visual": ("event_series@v1", "visual", True),
    "/event_asset": ("event_series@v1", "asset_set", True),
    "/event_asset_show": ("event_series@v1", "asset_show", True),
    "/event_asset_send": ("event_series@v1", "asset_send", True),
    "/event_visual_prep": ("event_series@v1", "stage_visual", True),
    "/event_content": ("event_series@v1", "content_mode", True),
    "/gen": ("event_series@v1", "gen", True),
    "/email_connect": ("event_series@v1", "email_connect", True),
    "/email_verify": ("event_series@v1", "email_verify", True),
    "/email_test": ("event_series@v1", "email_test", True),
    "/adproject": ("event_series@v1", "adproject", True),
    "/ad_spend_prepare": ("event_series@v1", "spend_prepare", True),
    "/ad_spend_consent": ("event_series@v1", "spend_consent", True),
    "/ad_spend_launch": ("event_series@v1", "spend_launch", True),
    "/ad_spend_stop": ("event_series@v1", "spend_stop", True),
    "/ad_spend_status": ("event_series@v1", "spend_status", True),
    "/ad_spend_process": ("event_series@v1", "spend_process", True),
    "/ad_goal_preview": ("event_series@v1", "goal_preview", True),
    "/business_retire": ("event_series@v1", "retire", True),
    "/business_retire_confirm": ("event_series@v1", "retire_confirm", True),
    "/business_retire_cancel": ("event_series@v1", "retire_cancel", True),
    "/business_restore": ("event_series@v1", "restore", True),
    "/event_video": ("event_series@v1", "video", True),
    "/event_ads": ("event_series@v1", "event_ads", True),
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
    "/ad_edit": ("business_admin@v1", "ad_edit", True),
    "/directions": ("business_admin@v1", "directions", True),
    "/direction": ("business_admin@v1", "direction", True),
    "/direction_add": ("business_admin@v1", "direction_add", True),
    "/direction_edit": ("business_admin@v1", "direction_edit", True),
    "/direction_goal": ("business_admin@v1", "direction_goal", True),
    "/direction_archive": ("business_admin@v1", "direction_archive", True),
    "/direction_restore": ("business_admin@v1", "direction_restore", True),
    "/offering_direction": ("business_admin@v1", "offering_direction", True),
    "/offerings": ("business_admin@v1", "offerings", True),
    "/offering_add": ("business_admin@v1", "offering_add", True),
    "/offering_retire": ("business_admin@v1", "offering_retire", True),
    "/offering_restore": ("business_admin@v1", "offering_restore", True),
    "/offering_process": ("business_admin@v1", "offering_process", True),
    "/offering_process_purge": ("business_admin@v1", "offering_process_purge", True),
    "/commerce": ("business_admin@v1", "commerce", True),
    "/commerce_check": ("business_admin@v1", "commerce_check", True),
    "/commerce_expand": ("business_admin@v1", "commerce_expand", True),
    "/formats": ("business_admin@v1", "formats", True),
    "/format_on": ("business_admin@v1", "format_on", True),
    "/format_off": ("business_admin@v1", "format_off", True),
    "/profile": ("business_admin@v1", "profile", True),
    "/profile_set": ("business_admin@v1", "profile_set", True),
    "/profile_details": ("business_admin@v1", "profile_details", True),
    "/profile_confirm": ("business_admin@v1", "profile_confirm", True),
    "/ad_stats": ("business_admin@v1", "ad_stats", True),
    "/ad_report": ("business_admin@v1", "ad_report", True),
    "/ad_creatives": ("business_admin@v1", "ad_creatives", True),
    "/ad_trial": ("business_admin@v1", "ad_trial", True),
    "/ad_trials": ("business_admin@v1", "ad_trials", True),
    "/ad_trial_view": ("business_admin@v1", "ad_trial_view", True),
    "/ad_trial_apply": ("business_admin@v1", "ad_trial_apply", True),
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
    "/lead_assign": ("sales_pipeline@v1", "assign", True),
    "/lead_claim": ("sales_pipeline@v1", "claim", True),
    "/leads_handoff": ("sales_pipeline@v1", "handoffs", True),
    "/leads_closed": ("sales_pipeline@v1", "closed", True),
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
    if session.get("source") == "managed_bot_update":  # Bot API managed_bot update, not user text
        mb = session.get("managed_bot") or {}
        arg = f"{str(mb.get('bot_id') or '')[:20]} {str(mb.get('username') or '')[:64]}"
        return propose("bot_provisioning@v1", {"user_id": user_id, "op": "managed_event", "arg": arg})
    data = str(getattr(ctx, "callback_data", "") or "")
    cbq = str(getattr(ctx, "callback_query_id", "") or "").strip()
    ack = {"callback_query_id": cbq} if cbq else {}  # stop the Telegram button spinner
    if data.startswith("cpm:") and ctx.is_admin:
        return propose("business_ops_summary@v1", {"user_id": user_id, "op": "cockpit", "arg": data[:120], **ack})
    if data.startswith("cpe:") and ctx.is_admin:
        return propose("event_series@v1", {"user_id": user_id, "op": "wizard", "arg": data[:64], **ack})
    args = str(ctx.args or "").strip()
    if ctx.cmd == "/customers" and ctx.is_admin:  # donor search_customers: id-fragment search screen
        q = re.sub(r"[^0-9A-Za-z_-]", "", args)[:40]
        return propose(
            "business_ops_summary@v1",
            {"user_id": user_id, "op": "cockpit", "arg": f"cpm:customers:{q}" if q else "cpm:customers"},
        )
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
    cap = 1200 if op == "event_schedule" else 200  # one line per session (up to 31)
    return propose(action, {"user_id": user_id, "op": op, "arg": str(ctx.args or "").strip()[:cap]})


__all__ = ["BUSINESS_FLOW_COMMANDS", "handle_business_flow_routes"]
