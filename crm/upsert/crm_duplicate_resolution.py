from __future__ import annotations


class CrmDuplicateResolution:
    def evaluate(self, *, matched: bool, merge_strategy: str) -> str:
        if not matched:
            return 'create'
        if merge_strategy == 'merge_non_empty':
            return 'update'
        return 'skip'
    decide = evaluate
