from __future__ import annotations

from uuid import uuid4


def new_learning_run_id() -> str:
    return f"learning_run_{uuid4().hex}"

def new_learning_batch_id() -> str:
    return f"learning_batch_{uuid4().hex}"

def new_policy_update_proposal_id() -> str:
    return f"policy_update_{uuid4().hex}"

def new_policy_snapshot_id() -> str:
    return f"policy_snapshot_{uuid4().hex}"
