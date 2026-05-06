from runtime.boot.web.observability_boot_plan import run_boot_item


def test_run_boot_item_disabled():
    called = {'value': False}

    def fn():
        called['value'] = True

    out = run_boot_item(key='x', enabled=False, fn=fn)
    assert out.key == 'x'
    assert out.enabled is False
    assert out.booted is False
    assert called['value'] is False


def test_run_boot_item_enabled():
    called = {'value': False}

    def fn():
        called['value'] = True

    out = run_boot_item(key='x', enabled=True, fn=fn)
    assert out.booted is True
    assert called['value'] is True
