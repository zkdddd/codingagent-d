from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import STATE_DIR

# Below this many failure records, recall honestly reports insufficient
# corpus rather than returning noisy near-duplicate matches.
_MIN_CORPUS_FOR_RECALL = 3
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./:]*")


@dataclass
class FailureRecord:
    run_id: str
    nodeid: str
    status: str
    failure_type: str = ""
    message: str = ""
    symbols: list[str] = field(default_factory=list)
    fix_hint: str = ""

    def text(self) -> str:
        parts = [self.nodeid, self.failure_type, self.message]
        if self.symbols:
            parts.append(" ".join(self.symbols))
        return " ".join(p for p in parts if p)


def collect_failure_corpus(
    runs_dir: str | Path | None = None,
    *,
    limit: int = 200,
) -> list[FailureRecord]:
    """Collect failure records from run logs, joining per-test failures with
    the symbol impacts and change plans recorded in the same run.
    """
    root = Path(runs_dir) if runs_dir is not None else Path(STATE_DIR) / "runs"
    if not root.exists():
        return []

    records: list[FailureRecord] = []
    for path in sorted(root.glob("*.jsonl")):
        if not path.is_file():
            continue
        try:
            events = _read_events(path)
        except (OSError, ValueError):
            continue
        run_id = _run_id(events) or path.stem
        symbols = _symbols_from_events(events)
        fix_hint = _fix_hint_from_events(events)
        for case in _failed_cases_from_events(events):
            records.append(
                FailureRecord(
                    run_id=run_id,
                    nodeid=str(case.get("nodeid") or ""),
                    status=str(case.get("status") or "failed"),
                    failure_type=str(case.get("failure_type") or ""),
                    message=str(case.get("message") or ""),
                    symbols=symbols,
                    fix_hint=fix_hint,
                )
            )
        if len(records) >= limit:
            break
    return records[:limit]


class FailureMemoryIndex:
    """A lightweight TF-IDF + cosine similarity index over failure records.

    No external dependencies and no embedding API: the corpus is small (a
    single-developer tool's run history), so a token-frequency index is
    honest and reproducible. When the corpus is too small, recall reports
    insufficient corpus instead of returning noisy matches.
    """

    def __init__(self, records: list[FailureRecord]) -> None:
        self.records = records
        self._doc_tokens = [_tokenize(rec.text()) for rec in records]
        self._idf = _compute_idf(self._doc_tokens)
        self._doc_vectors = [_tfidf_vector(tokens, self._idf) for tokens in self._doc_tokens]

    def recall_similar_failures(
        self,
        query: str,
        *,
        k: int = 5,
    ) -> dict[str, Any]:
        if len(self.records) < _MIN_CORPUS_FOR_RECALL:
            return {
                "ok": False,
                "reason": "insufficient_corpus",
                "corpus_size": len(self.records),
                "minimum_required": _MIN_CORPUS_FOR_RECALL,
                "matches": [],
            }
        query_tokens = _tokenize(query)
        query_vec = _tfidf_vector(query_tokens, self._idf)
        scored = []
        for idx, doc_vec in enumerate(self._doc_vectors):
            score = _cosine(query_vec, doc_vec)
            if score > 0:
                scored.append((score, idx))
        scored.sort(key=lambda item: (-item[0], item[1]))
        matches = []
        for score, idx in scored[:k]:
            rec = self.records[idx]
            matches.append(
                {
                    "score": round(score, 4),
                    "run_id": rec.run_id,
                    "nodeid": rec.nodeid,
                    "failure_type": rec.failure_type,
                    "message": rec.message[:200],
                    "symbols": rec.symbols,
                    "fix_hint": rec.fix_hint,
                }
            )
        return {
            "ok": True,
            "corpus_size": len(self.records),
            "matches": matches,
        }


def recall_similar_failures(
    query: str,
    runs_dir: str | Path | None = None,
    *,
    k: int = 5,
) -> dict[str, Any]:
    """Convenience: build the index from run logs and recall similar failures."""
    records = collect_failure_corpus(runs_dir)
    return FailureMemoryIndex(records).recall_similar_failures(query, k=k)


def _read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _run_id(events: list[dict[str, Any]]) -> str:
    for event in events:
        rid = event.get("run_id")
        if rid:
            return str(rid)
    return ""


def _failed_cases_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        if event.get("event") != "test_case_result":
            continue
        data = _event_data(event)
        status = str(data.get("status") or "")
        if status not in {"failed", "error"}:
            continue
        nodeid = str(data.get("nodeid") or "")
        if nodeid in seen:
            continue
        seen.add(nodeid)
        cases.append(data)
    return cases


def _symbols_from_events(events: list[dict[str, Any]]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for event in events:
        if event.get("event") != "symbol_impacts":
            continue
        data = _event_data(event)
        sym = str(data.get("symbol") or "")
        if sym and sym not in seen:
            seen.add(sym)
            symbols.append(sym)
    return symbols


def _fix_hint_from_events(events: list[dict[str, Any]]) -> str:
    # The change_plan event captures the edit intent; use its plan summary as a
    # lightweight "what was changed" hint when available.
    for event in reversed(events):
        if event.get("event") == "change_plan":
            data = _event_data(event)
            plan = data.get("plan")
            if isinstance(plan, dict):
                return str(plan.get("intent") or plan.get("summary") or "")[:200]
    return ""


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def _compute_idf(docs: list[list[str]]) -> dict[str, float]:
    n = len(docs)
    if n == 0:
        return {}
    df: dict[str, int] = {}
    for tokens in docs:
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1
    return {token: math.log((1 + n) / (1 + count)) + 1.0 for token, count in df.items()}


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    vec: dict[str, float] = {}
    for token in tokens:
        if token not in idf:
            continue
        vec[token] = vec.get(token, 0.0) + 1.0
    for token in vec:
        vec[token] *= idf[token]
    return vec


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(t, 0.0) * b.get(t, 0.0) for t in a.keys() & b.keys())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
