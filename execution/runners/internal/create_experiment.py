from __future__ import annotations

CANON_LEGACY_CREATE_EXPERIMENT_FAIL_CLOSED = True


class Runner:
    """Legacy dispatcher tripwire.

    Experiment creation must enter through create_experiment@v1 on the
    canonical RuntimeExecutor path so ActionIntent/PolicyDecision governance
    cannot be bypassed.
    """

    action_type = "create_experiment"

    def run(self, action):
        del action
        raise RuntimeError("CREATE_EXPERIMENT_REQUIRES_CANONICAL_RUNTIME_ACTION")
