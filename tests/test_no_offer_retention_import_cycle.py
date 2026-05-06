from __future__ import annotations

import sys


def test_offer_registry_import_does_not_import_retention_adapters():
    """Regression guard against import cycles.

    We check the *delta* in sys.modules caused by importing the offers registry.
    This keeps the test stable even if other tests imported retention earlier.
    """

    before = set(sys.modules.keys())

    import core.offers.catalog_registry as _reg  # noqa: F401

    after = set(sys.modules.keys())
    newly_imported = after - before

    assert "core.retention.decision_adapter" not in newly_imported
    assert "core.retention.adapters.retention_decision_adapter" not in newly_imported
