from canon.forbidden_shortcuts import FORBIDDEN_SHORTCUT_IMPORTS


def test_interfaces_cannot_import_decision():
    assert 'interfaces -> core.decision' in FORBIDDEN_SHORTCUT_IMPORTS
