from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    ROOT / "interfaces/messaging/_shared/provider_runtime.py",
    ROOT / "interfaces/web/chat_widget/outbound_sender.py",
)


def test_send_paths_use_guarded_send():
    offenders = []
    for path in TARGETS:
        text = path.read_text(encoding="utf-8")
        if "guarded_send(" not in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, offenders
