from __future__ import annotations

from runtime.platform.config import env_access, env_flags
from runtime.boot import env as runtime_env


def test_env_helpers_share_single_runtime_behavior() -> None:
    assert env_flags.env_str('MISSING_ENV_X', 'a') == env_access.env_str('MISSING_ENV_X', 'a')
    assert env_flags.env_int('MISSING_ENV_Y', 7) == env_access.env_int('MISSING_ENV_Y', 7)
    assert env_flags.env_float('MISSING_ENV_Z', 1.5) == env_access.env_float('MISSING_ENV_Z', 1.5)
    assert env_flags.env_bool('MISSING_ENV_Q', True) == env_access.env_bool('MISSING_ENV_Q', True)
    assert runtime_env.env_str('MISSING_ENV_W', 'b') == env_access.env_str('MISSING_ENV_W', 'b')
    assert runtime_env.env_int('MISSING_ENV_R', 9) == env_access.env_int('MISSING_ENV_R', 9)
    assert runtime_env.env_float('MISSING_ENV_T', 2.5) == env_access.env_float('MISSING_ENV_T', 2.5)
    assert runtime_env.env_bool('MISSING_ENV_U', False) == env_access.env_bool('MISSING_ENV_U', False)
