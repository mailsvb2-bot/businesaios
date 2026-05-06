from __future__ import annotations

"""
Telegram callback_data contract (canonical).

Keep ALL callback tokens in one place to avoid "god strings" scattered across
handlers/policies.

Rule: callback tokens are stable public API; change only with migration.
"""

# Main menu
CB_MENU_MAIN = "menu:main"

# Demo
CB_DEMO = "demo"
CB_DEMO_KIND_WORK = "demo_kind_work"
CB_DEMO_KIND_HOME = "demo_kind_home"

# Subscriptions / tariffs
CB_SUB_MENU = "sub:menu"
CB_PAY_SELECTED = "pay:selected"

# Gift / share
CB_GIFT_MENU = "gift:menu"
CB_GIFT_CREATE = "gift:create"
CB_SHARE_MENU = "share:menu"

# Settings
CB_SETTINGS_MENU = "settings:menu"
CB_SETTINGS_STATE = "settings:state"

# Weather
CB_WEATHER_SHOW = "weather:show"

# Admin
CB_ADMIN_MENU = "admin:menu"

# Autopilot ("one button" value)
CB_AUTOPILOT_MENU = "autopilot:menu"
CB_AUTOPILOT_START_7D = "autopilot:start:7d"
CB_AUTOPILOT_DIAG = "autopilot:diag"
CB_AUTOPILOT_OFFER = "autopilot:offer"
CB_AUTOPILOT_CHANNEL = "autopilot:channel"
CB_AUTOPILOT_LAUNCH = "autopilot:launch"
CB_AUTOPILOT_CLEAR_STOP_LOSS = "autopilot:stop_loss:clear"
CB_AUTOPILOT_DASHBOARD_TODAY = "autopilot:dash:today"
CB_AUTOPILOT_DASHBOARD_AUTOPILOT = "autopilot:dash:autopilot"
CB_AUTOPILOT_DASHBOARD_TASKS = "autopilot:dash:tasks"

# Ads apply (prod gate)
CB_ADS_APPLY_MENU = "ads:apply:menu"
CB_ADS_APPLY_ENABLE = "ads:apply:enable"
CB_ADS_APPLY_DISABLE = "ads:apply:disable"

# Ads Apply UI flow (pending plan -> preview -> confirm)
CB_ADS_APPLY_PREVIEW = "ads:apply:preview"
CB_ADS_APPLY_CONFIRM = "ads:apply:confirm"
CB_ADS_APPLY_CANCEL = "ads:apply:cancel"

# Profit Sprint (onboarding / one-week revenue sprint)
CB_PROFIT_SPRINT_START = "profit_sprint:start"
CB_PROFIT_SPRINT_LEAD_INBOX = "profit_sprint:lead:inbox"
CB_PROFIT_SPRINT_LEAD_CALLS = "profit_sprint:lead:calls"
CB_PROFIT_SPRINT_LEAD_SITE = "profit_sprint:lead:site"
CB_PROFIT_SPRINT_LEAD_SOCIAL = "profit_sprint:lead:social"
CB_PROFIT_SPRINT_LEAD_ADS = "profit_sprint:lead:ads"

# AI CEO
CB_CEO_MENU = "ceo:menu"
CB_CEO_PLAN = "ceo:plan"
CB_CEO_RUN = "ceo:run"


# Growth Strategy
CB_GROWTH_MENU = "growth:menu"
CB_GROWTH_GENERATE = "growth:generate"
CB_GROWTH_BACKLOG = "growth:backlog"
CB_GROWTH_ACCEPT_PREFIX = "growth:accept:"
CB_GROWTH_REJECT_PREFIX = "growth:reject:"
