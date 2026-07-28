from __future__ import annotations

from pathlib import Path


SAFETY_TEST_FILES = (
    "tests/integration/test_runtime_safety_upper_layers_wave218.py",
    "tests/integration/test_runtime_safety_upper_layers_wave219.py",
    "tests/integration/test_runtime_safety_upper_layers_wave220.py",
)


def replace_once(text: str, old: str, new: str, *, path: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old!r}")
    return text.replace(old, new, 1)


for raw_path in SAFETY_TEST_FILES:
    path = Path(raw_path)
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    monkeypatch.setenv('BUSINESAIOS_TENANT_CONFIG_AUDIT_LOG_PATH', str(tmp_path / 'tenant_config_audit.jsonl'))\n"
        "    build_safety_control_runtime.cache_clear()\n",
        "    monkeypatch.setenv('BUSINESAIOS_TENANT_CONFIG_AUDIT_LOG_PATH', str(tmp_path / 'tenant_config_audit.jsonl'))\n"
        "    monkeypatch.setenv('BUSINESAIOS_SAFETY_PERSISTENT', '1')\n"
        "    build_safety_control_runtime.cache_clear()\n",
        path=raw_path,
    )
    path.write_text(text, encoding="utf-8")

wave220 = Path("tests/integration/test_runtime_safety_upper_layers_wave220.py")
text = wave220.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from pathlib import Path\n",
    "from datetime import UTC, datetime, timedelta\nfrom pathlib import Path\n",
    path=str(wave220),
)
text = replace_once(
    text,
    "expires_at='2099-01-01T00:10:00+00:00'",
    "expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat()",
    path=str(wave220),
)
wave220.write_text(text, encoding="utf-8")

executor_test = Path("tests/runtime/test_executor_budget_consumed_after_safety.py")
text = executor_test.read_text(encoding="utf-8")
text = replace_once(
    text,
    "class _Guard:\n    _ledger = None\n\n    def execute_once(self, env):\n",
    "class _Guard:\n    _ledger = None\n\n    def verify(self, env):\n        return None\n\n    def execute_once(self, env):\n",
    path=str(executor_test),
)
executor_test.write_text(text, encoding="utf-8")
