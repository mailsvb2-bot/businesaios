from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from runtime.platform.business_memory.models import BusinessMemoryRecord
from runtime.platform.business_memory.policy import BusinessMemoryPolicy, DEFAULT_BUSINESS_MEMORY_POLICY
from runtime.platform.business_memory.semantics import counts_as_failure, counts_as_operator_handoff, counts_as_success


CANON_BUSINESS_MEMORY_COMPACTOR = True


def _unique_strings(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        token = str(item or '').strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
        if len(result) >= limit:
            break
    return result


def _compact_dict_items(items: list[dict[str, Any]], *, limit: int, dedupe_keys: tuple[str, ...] = ('action', 'status', 'reason')) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        entry = dict(item or {})
        marker = tuple(str(entry.get(key) or '').strip() for key in dedupe_keys)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(entry)
        if len(result) >= limit:
            break
    return result


def _run_signal(run: dict[str, Any]) -> tuple[str, str]:
    action = str(run.get('action') or '').strip()
    status = str(run.get('status') or '').strip()
    return action, status


@dataclass(frozen=True)
class BusinessMemoryCompactor:
    policy: BusinessMemoryPolicy = DEFAULT_BUSINESS_MEMORY_POLICY

    def compact(self, *, record: BusinessMemoryRecord) -> BusinessMemoryRecord:
        current = record.to_dict()
        recent_runs = [dict(item or {}) for item in list(current.get('recent_runs') or [])[: self.policy.max_recent_runs]]
        current['recent_runs'] = recent_runs
        current['active_channels'] = _unique_strings(list(current.get('active_channels') or []), limit=self.policy.max_active_channels)
        current['recent_external_refs'] = _unique_strings(list(current.get('recent_external_refs') or []), limit=self.policy.max_external_refs)
        current['last_verified_outcomes'] = _compact_dict_items(list(current.get('last_verified_outcomes') or []), limit=self.policy.max_verified_outcomes, dedupe_keys=('action', 'status'))
        current['failed_strategies'] = _compact_dict_items(list(current.get('failed_strategies') or []), limit=self.policy.max_failed_strategies, dedupe_keys=('action', 'status', 'reason'))
        current['current_campaigns'] = _compact_dict_items(list(current.get('current_campaigns') or []), limit=self.policy.max_campaigns, dedupe_keys=('action', 'status'))
        current['active_listings'] = _compact_dict_items(list(current.get('active_listings') or []), limit=self.policy.max_listings, dedupe_keys=('action', 'status'))
        current['open_leads'] = _compact_dict_items(list(current.get('open_leads') or []), limit=self.policy.max_open_leads, dedupe_keys=('action', 'status'))
        current['escalation_history'] = _compact_dict_items(list(current.get('escalation_history') or []), limit=self.policy.max_escalation_history, dedupe_keys=('action', 'reason'))

        win_counter: Counter[str] = Counter()
        failure_counter: Counter[str] = Counter()
        channel_counter: Counter[str] = Counter()
        ref_counter: Counter[str] = Counter()
        goal_counter: Counter[str] = Counter()
        operator_counter: Counter[str] = Counter()
        constraint_counter: Counter[str] = Counter()
        profile_segments: Counter[str] = Counter()

        for run in recent_runs:
            action, status = _run_signal(run)
            if not action:
                continue
            if counts_as_success(status):
                win_counter[action] += 1
            elif counts_as_failure(status):
                failure_counter[action] += 1
            elif counts_as_operator_handoff(status):
                operator_counter[action] += 1
            channel = str(run.get('channel') or '').strip()
            if channel:
                channel_counter[channel] += 1
            primary_ref = str(run.get('primary_ref') or '').strip()
            if primary_ref:
                ref_counter[primary_ref] += 1
            goal = str(run.get('goal') or '').strip()
            if goal:
                goal_counter[goal] += 1
            for key in run.get('constraint_keys') or []:
                token = str(key or '').strip()
                if token:
                    constraint_counter[token] += 1
        profile = dict(current.get('profile') or {})
        segment = str(profile.get('segment') or '').strip()
        if segment:
            profile_segments[segment] += 1

        current['recurring_wins'] = [
            {'action': action, 'count': count}
            for action, count in win_counter.most_common(self.policy.max_recurring_items)
            if count >= self.policy.recurring_win_threshold
        ]
        current['recurring_failures'] = [
            {'action': action, 'count': count}
            for action, count in failure_counter.most_common(self.policy.max_recurring_items)
            if count >= self.policy.recurring_failure_threshold
        ]

        current['learned_preferences'] = {
            'preferred_channels': [channel for channel, _ in channel_counter.most_common(3)],
        }
        current['active_goals'] = [goal for goal, _ in goal_counter.most_common(5)]
        current['operating_constraints'] = {
            'constraint_keys': [key for key, _ in constraint_counter.most_common(8)],
            'operator_handoffs_count': sum(operator_counter.values()),
        }
        current['aggregated_business_profile'] = {
            'segment': segment,
            'active_channels_count': len(current.get('active_channels') or []),
            'verified_outcomes_count': len(current.get('last_verified_outcomes') or []),
            'operator_handoffs_count': len(current.get('escalation_history') or []),
            'recent_external_refs_count': len(current.get('recent_external_refs') or []),
            'top_external_refs': [ref for ref, _ in ref_counter.most_common(5)],
            'profile_segments_seen': [name for name, _ in profile_segments.most_common(3)],
        }
        return BusinessMemoryRecord.from_dict(current, business_id=record.business_id)


__all__ = [
    'CANON_BUSINESS_MEMORY_COMPACTOR',
    'BusinessMemoryCompactor',
]
