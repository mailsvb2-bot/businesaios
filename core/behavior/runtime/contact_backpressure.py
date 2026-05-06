from __future__ import annotations

def should_throttle_contact(contact_constraints: dict[str, object], current_attempts: int) -> bool:
    cap = int(contact_constraints.get("contact_frequency_cap", 0))
    if cap <= 0:
        return False
    return current_attempts >= cap
