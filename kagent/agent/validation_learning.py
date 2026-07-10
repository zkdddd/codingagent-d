from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import STATE_DIR
from .run_log import read_run_events


@dataclass
class _CommandStats:
    label: str
    command: str
    cwd: str
    timeout_ms: int
    successes: int = 0
    failures: int = 0
    last_seen: str = ""

    @property
    def attempts(self) -> int:
        return self.successes + self.failures

    @property
    def failure_rate(self) -> float:
        if not self.attempts:
            return 0.0
        return self.failures / self.attempts


def learned_validation_commands_from_runs(
    runs_dir: str | Path | None = None,
    *,
    min_successes: int = 1,
    max_failure_rate: float = 0.5,
    limit: int = 5,
) -> list[dict[str, Any]]:
    root = Path(runs_dir) if runs_dir is not None else Path(STATE_DIR) / "runs"
    if not root.exists():
        return []

    stats: dict[tuple[str, str], _CommandStats] = {}
    for path in sorted(root.glob("*.jsonl")):
        if not path.is_file():
            continue
        try:
            events = read_run_events(path)
        except (OSError, ValueError):
            continue
        for command_info, ok, timestamp in _validation_command_results(events):
            command = str(command_info.get("command") or "").strip()
            if not command:
                continue
            cwd = str(command_info.get("cwd") or ".")
            key = (command, cwd)
            item = stats.get(key)
            if item is None:
                item = _CommandStats(
                    label=str(command_info.get("label") or "Learned validation"),
                    command=command,
                    cwd=cwd,
                    timeout_ms=int(command_info.get("timeout_ms") or 120000),
                )
                stats[key] = item
            if ok:
                item.successes += 1
            else:
                item.failures += 1
            if timestamp:
                item.last_seen = str(timestamp)

    learned = [
        item
        for item in stats.values()
        if item.successes >= min_successes and item.failure_rate <= max_failure_rate
    ]
    learned.sort(
        key=lambda item: (
            item.successes,
            -item.failures,
            item.last_seen,
            item.command,
        ),
        reverse=True,
    )
    return [_command_to_dict(item) for item in learned[:limit]]


def _validation_command_results(
    events: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], bool, str | None]]:
    planned = _planned_validation_commands(events)
    if not planned:
        return []

    results: list[tuple[dict[str, Any], bool, str | None]] = []
    for event in events:
        data = _event_data(event)
        if event.get("event") != "tool_result" or data.get("name") != "run_command":
            continue
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        command = str(args.get("command") or "").strip()
        cwd = str(args.get("cwd") or ".")
        command_info = planned.get((command, cwd)) or planned.get((command, "."))
        if command_info is None:
            continue
        results.append((command_info, _tool_result_ok(data), event.get("timestamp")))
    return results


def _planned_validation_commands(events: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    planned: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        data = _event_data(event)
        if event.get("event") != "tool_result" or data.get("name") != "validation_plan":
            continue
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        commands = result.get("commands") if isinstance(result.get("commands"), list) else []
        for command_info in commands:
            if not isinstance(command_info, dict):
                continue
            command = str(command_info.get("command") or "").strip()
            if not command:
                continue
            cwd = str(command_info.get("cwd") or ".")
            planned[(command, cwd)] = command_info
    return planned


def _tool_result_ok(data: dict[str, Any]) -> bool:
    if "ok" in data:
        return bool(data.get("ok"))
    result = data.get("result")
    if isinstance(result, dict):
        if "ok" in result:
            return bool(result.get("ok"))
        if "returncode" in result:
            return int(result.get("returncode") or 0) == 0
    return True


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _command_to_dict(item: _CommandStats) -> dict[str, Any]:
    confidence = item.successes / max(1, item.attempts)
    return {
        "label": item.label,
        "reason": (
            "Learned from previous successful Agent validation runs "
            f"({item.successes} pass, {item.failures} fail)."
        ),
        "command": item.command,
        "cwd": item.cwd,
        "timeout_ms": item.timeout_ms,
        "learned": True,
        "success_count": item.successes,
        "failure_count": item.failures,
        "confidence": round(confidence, 3),
        "last_seen": item.last_seen,
    }
