from __future__ import annotations

import importlib
from pathlib import Path


def test_runtime_ads_modules_use_public_surfaces() -> None:
    targets = {
        "runtime/boot/ads_apply_provider": ["bootstrap/ads_apply_provider.py", "runtime.ads"],
        "runtime/boot/ads_wiring": ["bootstrap/ads_wiring.py", "runtime.ads", "runtime.actions"],
        "runtime/boot/ads_write_gateway": ["bootstrap/ads_write_gateway.py", "runtime.ads"],
        "runtime/boot/builders/ads_autopilot.py": [None, "runtime.ads"],
        "runtime/boot/builders/ads_rl.py": [None, "runtime.ads"],
        "runtime/boot/handler_groups/ads.py": [None, "runtime.actions"],
        "runtime/handlers/ads_apply_execute.py": [None, "runtime.ads", "runtime.governance"],
        "runtime/handlers/ads_apply_helpers.py": [None, "runtime.ads"],
        "runtime/handlers/ads_autopilot_gate.py": [None, "runtime.governance"],
        "runtime/handlers/ads_autopilot_tick.py": [None, "runtime.governance"],
        "runtime/handlers/ads_rl_report.py": [None, "runtime.ads"],
        "runtime/handlers/ads_rl_suggest.py": [None, "runtime.ads", "runtime.governance"],
        "runtime/handlers/ads_rl_train_tick.py": [None, "runtime.ads", "runtime.governance"],
        "runtime/handlers/ads_autopilot/gate.py": [None, "runtime.governance"],
        "runtime/handlers/ads_autopilot/request_builder.py": [None, "runtime.ads"],
        "runtime/handlers/ads_autopilot_tick_parts/engine_contract.py": [None, "runtime.ads"],
        "runtime/jobs/ads_autopilot_tick.py": [None, "runtime.ads"],
        "runtime/jobs/ads_rl_observer_job.py": [None, "runtime.ads"],
    }
    forbidden_prefixes = (
        "from core.ads", "import core.ads", "from core.growth.ads", "import core.growth.ads",
        "from core.growth.autopilot_scheduler", "import core.growth.autopilot_scheduler",
        "from core.growth.budget_guardrails", "import core.growth.budget_guardrails",
        "from core.growth.circuit_breaker", "import core.growth.circuit_breaker",
        "from core.growth.event_sink", "import core.growth.event_sink",
        "from core.governance", "import core.governance",
        "from core.actions.action_names", "import core.actions.action_names",
    )
    for rel, required_imports in targets.items():
        owner_path, *needles = required_imports
        if owner_path is not None:
            _ = Path(rel).name
            alias = importlib.import_module(rel.replace('/', '.'))
            assert hasattr(alias, '__getattr__') or alias is not None
            text = Path(owner_path).read_text(encoding='utf-8')
        else:
            text = Path(rel).read_text(encoding='utf-8')
        for required in needles:
            assert required in text, rel
        for forbidden in forbidden_prefixes:
            assert forbidden not in text, rel
