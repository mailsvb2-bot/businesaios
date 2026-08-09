from __future__ import annotations

from dataclasses import replace

from runtime.messaging.outbound_message import OutboundMessage


def _execution_blocked(meta: object) -> bool:
    return isinstance(meta, dict) and str(meta.get("mode") or "").strip().casefold() == "blocked"


def _guard_blocks(attempt_guard, msg) -> bool:
    if attempt_guard is None:
        return False
    try:
        return bool(str(attempt_guard(msg) or '').strip())
    except Exception:
        return True


def execute_policy_plan_with_events(
    *,
    plan,
    base_message: OutboundMessage,
    send_once,
    recorder=None,
    attempt_guard=None,
):
    attempts = []
    last_meta = {}

    if not plan.ordered_channels:
        if recorder is not None:
            recorder.record_plan(msg=base_message, plan=plan)
            recorder.record_finished(
                msg=base_message,
                plan=plan,
                selected_channel='',
                terminal_reason=str(plan.terminal_reason or 'no_eligible_channel'),
                attempts_count=0,
            )
        return False, {
            'policy': {
                'ordered_channels': [],
                'reason_codes': list(plan.reason_codes),
                'terminal_reason': plan.terminal_reason,
                'attempts': [],
            }
        }

    plan_recorded = False
    for channel in plan.ordered_channels:
        msg = replace(base_message, channel=channel, transport_guard=attempt_guard)
        if _guard_blocks(attempt_guard, msg):
            return False, {}
        if recorder is not None and not plan_recorded:
            recorder.record_plan(msg=base_message, plan=plan)
            plan_recorded = True
        ok, meta = send_once(msg)
        meta = dict(meta or {})
        if _execution_blocked(meta):
            return False, {}
        attempts.append({'channel': channel, 'ok': bool(ok), 'meta': meta})
        last_meta = meta

        if recorder is not None:
            recorder.record_attempt(msg=msg, ok=bool(ok), meta=meta)

        if ok:
            if recorder is not None:
                recorder.record_finished(
                    msg=base_message,
                    plan=plan,
                    selected_channel=channel,
                    terminal_reason='',
                    attempts_count=len(attempts),
                )
            out = dict(meta)
            out['policy'] = {
                'ordered_channels': list(plan.ordered_channels),
                'reason_codes': list(plan.reason_codes),
                'terminal_reason': plan.terminal_reason,
                'attempts': attempts,
                'selected_channel': channel,
            }
            return True, out

    if recorder is not None:
        recorder.record_finished(
            msg=base_message,
            plan=plan,
            selected_channel='',
            terminal_reason='all_attempts_failed',
            attempts_count=len(attempts),
        )

    out = dict(last_meta or {})
    out['policy'] = {
        'ordered_channels': list(plan.ordered_channels),
        'reason_codes': list(plan.reason_codes),
        'terminal_reason': 'all_attempts_failed',
        'attempts': attempts,
    }
    return False, out
