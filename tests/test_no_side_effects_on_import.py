import os
import sys


def test_imports_do_not_mutate_env_or_sys_flags():
    env_before = dict(os.environ)
    dont_write_before = sys.dont_write_bytecode

    # Import core/runtime modules (should be pure).
    import core  # noqa: F401
    import governance  # noqa: F401
    import runtime  # noqa: F401

    assert dict(os.environ) == env_before
    assert sys.dont_write_bytecode == dont_write_before
