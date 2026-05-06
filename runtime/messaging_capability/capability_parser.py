from __future__ import annotations

from runtime.messaging_capability.capability_requirement import CapabilityRequirement


def parse_capability_requirement(value) -> CapabilityRequirement:
    if not isinstance(value, dict):
        return CapabilityRequirement()
    return CapabilityRequirement(
        plain_text=bool(value.get("plain_text", True)),
        html=bool(value.get("html", False)),
        buttons=bool(value.get("buttons", False)),
        attachments=bool(value.get("attachments", False)),
        structured_payload=bool(value.get("structured_payload", False)),
        subject_line=bool(value.get("subject_line", False)),
    )
