from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import STATE_DIR


class RunLogger:
    def __init__(self, session_id: str | None, workspace_root: str):
        self.run_id = uuid.uuid4().hex
        self.session_id = session_id
        self.workspace_root = workspace_root
        self.started_at = _utc_now()
        self.path = Path(STATE_DIR) / "runs" / f"{self.started_at[:10]}-{self.run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.write(
            "run_start",
            {
                "session_id": session_id,
                "workspace_root": workspace_root,
            },
        )

    def write(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        event = {
            "timestamp": _utc_now(),
            "run_id": self.run_id,
            "event": event_type,
            "data": _sanitize(data or {}),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def finish(self, status: str, data: dict[str, Any] | None = None) -> None:
        payload = dict(data or {})
        payload["status"] = status
        self.write("run_finish", payload)


def read_run_events(path: str | Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid run log JSON on line {line_no}: {exc}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"Invalid run log event on line {line_no}: expected object")
        events.append(event)
    return events


def summarize_run_log(path: str | Path) -> dict[str, Any]:
    events = read_run_events(path)
    event_counts = Counter(str(event.get("event") or "unknown") for event in events)
    status_events = [event for event in events if event.get("event") == "agent_status"]
    tool_events = [event for event in events if event.get("event") == "tool_call"]
    model_request_events = [event for event in events if event.get("event") == "model_request"]
    finish = next((event for event in reversed(events) if event.get("event") == "run_finish"), None)
    start = next((event for event in events if event.get("event") == "run_start"), None)

    changed_paths: list[str] = []
    if finish and isinstance(finish.get("data"), dict):
        raw_paths = finish["data"].get("changed_paths") or []
        if isinstance(raw_paths, list):
            changed_paths = [str(path) for path in raw_paths]

    return {
        "path": str(Path(path)),
        "run_id": events[0].get("run_id") if events else None,
        "session_id": _event_data(start).get("session_id") if start else None,
        "workspace_root": _event_data(start).get("workspace_root") if start else None,
        "started_at": events[0].get("timestamp") if events else None,
        "finished_at": finish.get("timestamp") if finish else None,
        "status": _event_data(finish).get("status") if finish else None,
        "event_count": len(events),
        "event_counts": dict(event_counts),
        "last_phase": _last_phase(status_events),
        "tool_call_count": len(tool_events),
        "model_request_count": len(model_request_events),
        "changed_paths": changed_paths,
        "validation_failed": bool(_event_data(finish).get("validation_failed")) if finish else False,
        "last_validation_summary": _event_data(finish).get("last_validation_summary") if finish else None,
    }


def latest_run_log(runs_dir: str | Path | None = None) -> Path | None:
    root = Path(runs_dir) if runs_dir is not None else Path(STATE_DIR) / "runs"
    if not root.exists():
        return None
    logs = [path for path in root.glob("*.jsonl") if path.is_file()]
    if not logs:
        return None
    return max(logs, key=_run_log_sort_key)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_log_sort_key(path: Path) -> tuple[str, int, str]:
    timestamp = ""
    try:
        events = read_run_events(path)
    except ValueError:
        events = []
    for event in reversed(events):
        if event.get("timestamp"):
            timestamp = str(event["timestamp"])
            break
    return (timestamp, path.stat().st_mtime_ns, path.name)


def _event_data(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {}
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _last_phase(status_events: list[dict[str, Any]]) -> str | None:
    for event in reversed(status_events):
        data = _event_data(event)
        phase = data.get("phase")
        if phase:
            return str(phase)
    return None


def _sanitize(value: Any, *, max_text: int = 4000) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        if len(value) <= max_text:
            return value
        return value[: max_text - 24] + "\n... (log clipped)"
    if isinstance(value, dict):
        return {str(key): _sanitize(item, max_text=max_text) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, max_text=max_text) for item in value[:100]]
    return str(value)
