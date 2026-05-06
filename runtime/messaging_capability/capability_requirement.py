from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityRequirement:
    plain_text: bool = True
    html: bool = False
    buttons: bool = False
    attachments: bool = False
    structured_payload: bool = False
    subject_line: bool = False
