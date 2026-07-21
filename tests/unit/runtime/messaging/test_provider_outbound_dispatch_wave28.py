from __future__ import annotations

import pytest

import runtime._internal.effects_clients.provider_outbound_sender as sender
from tests.unit.runtime.messaging._provider_outbound_transport_support_wave28 import _cfg, _msg


def test_send_outbound_dispatches_without_changing_public_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    msg = _msg()
    assert sender.send_outbound(cfg=_cfg(mode=sender.NOOP_MODE), msg=msg)["noop"] is True

    monkeypatch.setattr(sender, "_send_webhook", lambda *, cfg, msg: {"kind": "webhook", "cfg": cfg, "msg": msg})
    assert sender.send_outbound(cfg=_cfg(mode="webhook"), msg=msg)["kind"] == "webhook"

    monkeypatch.setattr(sender, "_send_smtp", lambda *, cfg, msg: {"kind": "smtp", "cfg": cfg, "msg": msg})
    assert sender.send_outbound(cfg=_cfg(mode="smtp"), msg=msg)["kind"] == "smtp"

    unsupported = sender.send_outbound(cfg=_cfg(mode="other"), msg=msg)
    assert unsupported["reason"] == "provider_mode_unsupported"
