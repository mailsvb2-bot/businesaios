import pytest


def test_allow_internal_import_is_executor_only():
    """Security invariant: Only runtime.executor can open internal import window."""
    from runtime.firewall.import_guard import allow_internal_import

    with pytest.raises(PermissionError):
        with allow_internal_import():
            # If we got here, firewall is broken.
            pass


def test_executor_can_import_internal_effects():
    """Sanity check: executor path still works."""
    import runtime.executor as ex

    assert hasattr(ex, "RuntimeExecutor")
