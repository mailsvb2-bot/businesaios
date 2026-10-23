from application.business_flows import cockpit as cp
from runtime.handler_impl.domains import business_flow_ops as ops


def test_parse_and_navigation() -> None:
    assert cp.parse("cpm:bookings:2") == cp.Parsed("bookings", ("2",))
    assert cp.parse("cpm:BAD").action == "stale" and cp.parse("x").action == "stale"
    text, rows = cp.render(cp.parse("cpm:today"), cp.Snapshot(), is_owner=True)
    assert "сегодня" in text and rows[-1] == [("⬅️ Назад", "cpm:work"), cp.HOME]
    assert cp.render(cp.parse("cpm:menu"), cp.Snapshot(), is_owner=False)[0].startswith("Для Вашей роли")
    assert "неактуальна" in cp.render(cp.parse("cpm:bookings:9"), cp.Snapshot(slots=[1]), is_owner=True)[0]


def test_paging() -> None:
    class P:
        def __init__(self, n):
            self.name = f"P{n}"

    snap = cp.Snapshot(partners=[P(i) for i in range(8)])
    text, rows = cp.render(cp.parse("cpm:partners:0"), snap, is_owner=True)
    assert "P5" in text and "P6" not in text and rows[0] == [("Вперёд ➡️", "cpm:partners:1")]


def test_cockpit_handler_sends_keyboard(flow) -> None:
    flow.run(ops.handle_partners, op="add", arg="Кофейня Зерно | кофе | 9000 | existing | @zerno")
    _, text = flow.run(ops.handle_business_ops_summary, op="cockpit", arg="cpm:partners:0")
    assert "Кофейня Зерно" in text
    kb = flow.effects.sent[-1]["reply_markup"]["inline_keyboard"]
    assert kb[-1][0]["callback_data"] == "cpm:growth"


def test_cockpit_route() -> None:
    from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes

    class Ctx:
        cmd, args, callback_data, is_admin = "", "", "cpm:today", True

    out = handle_business_flow_routes(Ctx(), user_id="u1")
    assert out.action == "business_ops_summary@v1" and out.payload["arg"] == "cpm:today"
    Ctx.is_admin = False
    assert handle_business_flow_routes(Ctx(), user_id="u1") is None
