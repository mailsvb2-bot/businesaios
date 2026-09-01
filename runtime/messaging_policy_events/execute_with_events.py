from __future__ import annotations

from dataclasses import replace

from runtime.messaging.outbound_message import OutboundMessage, transport_guard_blocks


def _execution_blocked(meta: object) -> bool:
    return isinstance(meta, dict) and str(meta.get("mode") or "").strip().casefold() == "blocked"


def _execution_pending(meta: object) -> str:
    if not isinstance(meta, dict):
        return ""
    mode = str(meta.get("mode") or "").strip().casefold()
    return mode if mode in {"approval_required", "in_progress"} else ""



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
        if transport_guard_blocks(attempt_guard, msg):
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

        pending_mode = _execution_pending(meta)
        if pending_mode:
            if recorder is not None:
                recorder.record_finished(
                    msg=base_message,
                    plan=plan,
                    selected_channel='',
                    terminal_reason=pending_mode,
                    attempts_count=len(attempts),
                )
            out = dict(meta)
            out['policy'] = {
                'ordered_channels': list(plan.ordered_channels),
                'reason_codes': list(plan.reason_codes),
                'terminal_reason': pending_mode,
                'attempts': attempts,
                'selected_channel': '',
            }
            return False, out

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
