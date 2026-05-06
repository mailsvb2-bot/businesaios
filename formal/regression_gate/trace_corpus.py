from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .replay_harness import ReplayCase


@dataclass(frozen=True)
class TraceCorpusEntry:
    name: str
    payload: dict[str, Any]
    expected_contract: dict[str, Any]
    expected_trace: dict[str, Any]

    def to_replay_case(self) -> ReplayCase:
        return ReplayCase(
            name=self.name,
            payload=self.payload,
            expected_contract=self.expected_contract,
            expected_trace=self.expected_trace,
        )



def corpus_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "trace_corpus"



def load_trace_corpus(root: Path | None = None) -> list[TraceCorpusEntry]:
    base = root or corpus_root()
    entries: list[TraceCorpusEntry] = []
    for path in sorted(base.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries.append(
            TraceCorpusEntry(
                name=payload["name"],
                payload=payload["payload"],
                expected_contract=payload["expected_contract"],
                expected_trace=payload["expected_trace"],
            )
        )
    return entries



def replay_cases_from_corpus(root: Path | None = None) -> list[ReplayCase]:
    return [entry.to_replay_case() for entry in load_trace_corpus(root)]



def summarize_corpus(root: Path | None = None) -> dict[str, Any]:
    entries = load_trace_corpus(root)
    names = tuple(entry.name for entry in entries)
    return {
        "count": len(entries),
        "names": names,
        "ok": bool(entries),
    }
