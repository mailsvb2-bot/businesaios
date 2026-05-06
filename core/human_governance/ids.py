from __future__ import annotations

from uuid import uuid4


def new_review_id() -> str:
    return f"review_{uuid4().hex}"


def new_override_id() -> str:
    return f"override_{uuid4().hex}"


def new_escalation_id() -> str:
    return f"escalation_{uuid4().hex}"
