from pathlib import Path

from runtime.boot.finalize_runtime_args import FinalizeRuntimeArgs
from runtime.runtime_infra import RuntimeInfra


def test_finalize_runtime_args_keeps_runtime_infra_surface():
    infra = RuntimeInfra(event_store="ev", ledger="ledger", settings_gateway="gw")
    args = FinalizeRuntimeArgs(
        stack="stack",
        keyring="keyring",
        schemas="schemas",
        event_log="event_log",
        preg="preg",
        policy_selector="selector",
        handlers="handlers",
        model_registry="registry",
        issuer_id="businesaios-core",
        repo_root=Path('.'),
        event_store="ev",
        base="/tmp/base",
        runtime_infra=infra,
    )
    assert args.runtime_infra.event_store == "ev"
    assert args.runtime_infra.settings_store == "gw"
