from application.business_flows import cockpit as cp


TEAM = {"roles": {"77": ["admin"], "88": ["marketing"]}, "perms": {"88": ["ads.read"]}}


def _r(data, team=TEAM):
    return cp.render(cp.parse(data), cp.Snapshot(team=team), is_owner=True)


def test_team_lists_members_with_roles_and_buttons():
    text, rows = _r("cpm:team:0")
    assert "77 — администратор" in text and "88 — маркетинг" in text
    assert ("👤 77", "cpm:member:77") in [b for r in rows for b in r]


def test_member_card_shows_roles_and_perms_and_is_read_only():
    text, rows = _r("cpm:member:88")
    assert "Роли: маркетинг" in text and "Права: ads.read" in text
    assert rows[-1][0] == ("⬅️ Назад", "cpm:team:0")


def test_unknown_member_is_stale_and_empty_team():
    assert "неактуальна" in _r("cpm:member:999")[0]
    assert "никого нет" in _r("cpm:team:0", team={})[0]


def test_manage_links_team():
    assert ("👥 Команда", "cpm:team:0") in [b for r in _r("cpm:manage")[1] for b in r]


def test_handler_reads_roles_from_event_store(flow):
    from runtime.handler_impl.domains.business_flow_ops import handle_business_ops_summary

    for uid, role, on in (("77", "admin", True), ("88", "marketing", True), ("88", "marketing", False)):
        flow.store.events.append(
            {
                "tenant_id": "t1",
                "user_id": "u1",
                "event_type": "admin_role_set",
                "timestamp_ms": 0,
                "payload": {"target_user_id": uid, "role": role, "enabled": on},
            }
        )
    flow.run(handle_business_ops_summary, op="cockpit", arg="cpm:team:0")
    text = flow.effects.sent[-1]["text"]
    assert "77 — администратор" in text and "88 — без ролей" in text
