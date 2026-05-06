from runtime.boot.core_assembly_args import CoreAssemblyArgs
from runtime.executor_infra import RuntimeExecutorInfra


def test_core_assembly_args_keep_executor_infra():
    infra = RuntimeExecutorInfra(ledger="ledger", outbox="outbox", snapshot_store="snap")
    args = CoreAssemblyArgs(
        keyring="k",
        schemas="s",
        event_log="elog",
        decision_archive="archive",
        policy_registry="preg",
        policy_selector="selector",
        handlers="handlers",
        runtime_infra=infra,
        delivery_state="delivery",
    )
    assert args.runtime_infra.decision_ledger == "ledger"
    assert args.runtime_infra.effect_outbox == "outbox"
