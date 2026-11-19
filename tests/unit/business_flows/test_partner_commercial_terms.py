from __future__ import annotations

import pytest

from application.business_flows import partners as terms
from application.business_flows import partners as pt
from runtime.handler_impl.domains.business_flow_ops import handle_partners


def test_quotes_require_strict_minor_units_and_explicit_owner_decision():
    pid = pt.parse_partner("Студия | wellness | 100 | existing | @studio")["partner_id"]
    quote = terms.create_quote(pid, "1500000", "RUB", "Размещение на 7 дней")
    assert quote["amount_minor"] == 1500000
    assert quote["status"] == "pending_owner_approval"
    assert terms.decision([quote], quote["quote_id"], approve=True)["approval_scope"] == "internal_only_no_send_no_payment"
    decided = [quote, terms.decision([quote], quote["quote_id"], approve=True)]
    assert terms.quote_states(decided)[quote["quote_id"]]["status"] == "owner_approved"
    assert terms.decision(decided, quote["quote_id"], approve=True) is None
    with pytest.raises(ValueError):
        terms.decision(decided, quote["quote_id"], approve=False)
    for invalid in ["-1", "1.2", "1e4", "0", "00100000000000"]:
        with pytest.raises(ValueError):
            terms.create_quote(pid, invalid, "RUB", "Размещение")


def test_quote_flow_is_event_sourced_and_never_sends_to_partner(flow):
    flow.run(handle_partners, op="add", arg="Студия | wellness | 100 | existing | @studio")
    pid = pt.parse_partner("Студия | wellness | 100 | existing | @studio")["partner_id"]
    _, text = flow.run(handle_partners, op="quote", arg=f"{pid} | 1500000 | RUB | Пост")
    assert "не договор" in text
    _, listed = flow.run(handle_partners, op="quotes")
    assert "15000,00 RUB" in listed
    quote_id = terms.create_quote(pid, "1500000", "RUB", "Пост")["quote_id"]
    _, approved = flow.run(handle_partners, op="approve_quote", arg=quote_id)
    assert "Контрагенту не отправлено" in approved
    _, repeat = flow.run(handle_partners, op="approve_quote", arg=quote_id)
    assert "уже учтено" in repeat
    _, rank = flow.run(handle_partners, op="rank")
    assert pid in rank


def test_clientplatform_partner_menu_is_real_command_owner():
    from core.ux.unified_messenger_menu import menu_items, telegram_menu
    from core.policies.telegram.routes.business_flow_routes import BUSINESS_FLOW_COMMANDS
    entries = {item.key: item.callback for item in menu_items(role="owner", is_admin=True)}
    assert entries["partners"] == "cp:section:partners"
    assert BUSINESS_FLOW_COMMANDS["/partners"][:2] == ("partners@v1", "rank")
    assert BUSINESS_FLOW_COMMANDS["/partner_quotes"][:2] == ("partners@v1", "quotes")
    buttons = telegram_menu(role="owner", is_admin=True)["inline_keyboard"]
    assert any(button.get("callback_data") == "cp:section:partners" for row in buttons for button in row)
