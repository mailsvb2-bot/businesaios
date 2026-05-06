import importlib

import pytest

from runtime.firewall.import_guard import activate_import_firewall, deactivate_import_firewall


def test_direct_effect_import_blocked():
    activate_import_firewall()
    try:
        with pytest.raises(ImportError):
            __import__("runtime.executor.effects_impl")
    finally:
        deactivate_import_firewall()


def test_from_import_blocked():
    activate_import_firewall()
    try:
        with pytest.raises(ImportError):
            from runtime.executor import effects_impl  # noqa
    finally:
        deactivate_import_firewall()


def test_importlib_blocked():
    activate_import_firewall()
    try:
        with pytest.raises(ImportError):
            importlib.import_module("runtime.executor.effects_impl")
    finally:
        deactivate_import_firewall()
