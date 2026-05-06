from __future__ import annotations

from execution.runners.internal._base import AcceptedInternalRunner


class Runner(AcceptedInternalRunner):
    action_type = 'create_experiment'
    message = 'experiment_created'
