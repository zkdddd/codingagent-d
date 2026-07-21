from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .run_history import list_run_history
from .run_log import read_run_events
from .test_telemetry import normalize_pytest_command

# Timing regression tuning. Median baseline resists outliers; a regression is
# flagged only when the latest run is both meaningfully slower in ratio AND in
# absolute delta (so fast tests are not flagged on tiny jitter).
_TIMING_BASELINE_WINDOW = 5
_TIMING_REGRESSION_RATIO = 1.5
_TIMING_MIN_DELTA_MS = 200
_TIMING_MIN_BASELINE_SAMPLES = 2
_TIMING_TREND_STABLE_RATIO = 0.1
_TIMING_TREND_SERIES_LIMIT = 12
_TIMING_TOP_LIMIT = 8


def build_run_analytics(
    runs_dir: str | Path | None = None,
    *,
    limit: int = 50,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    rows = list_run_history(runs_dir, limit=max(0, int(limit)))
    workspace = str(workspace_root or "").strip()
    if workspace:
        rows = [row for row in rows if str(row.get("workspace_root") or "").strip() == workspace]
    counters = _base_counters(rows)
    issue_counts: Counter[str] = Counter()
    gate_check_counts: Counter[str] = Counter()
    failed_tool_counts: Counter[str] = Counter()
    model_error_counts: Counter[str] = Counter()
    validation_command_counts: Counter[str] = Counter()
    test_status_counts: Counter[str] = Counter()
    failed_test_counts: Counter[str] = Counter()
    slowest_tests: dict[str, int] = {}
    nodeid_durations: dict[str, list[dict[str, Any]]] = {}
    command_durations: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        for issue in row.get("issue_codes") or []:
            issue_counts[str(issue)] += 1
        started_at = row.get("started_at")
        events = _safe_read_events(row.get("path"))
        gate_check_counts.update(_gate_check_counts(events))
        failed_tool_counts.update(_failed_tool_counts(events))
        model_error_counts.update(_model_error_counts(events))
        validation_command_counts.update(_validation_command_counts(events))
        test_counts, failed_tests, slow_tests, run_durations = _test_case_counts(events)
        test_status_counts.update(test_counts)
        failed_test_counts.update(failed_tests)
        for nodeid, duration_ms in slow_tests.items():
            slowest_tests[nodeid] = max(slowest_tests.get(nodeid, 0), duration_ms)
        for nodeid, info in run_durations.items():
            nodeid_durations.setdefault(nodeid, []).append(
                {
                    "ts": started_at,
                    "ms": int(info.get("ms") or 0),
                    "status": str(info.get("status") or ""),
                }
            )
        for command, cmd_ms in _validation_command_durations(events).items():
            command_durations.setdefault(command, []).append({"ts": started_at, "ms": cmd_ms})

    run_count = len(rows)
    return {
        "run_count": run_count,
        "status_counts": dict(counters["status"]),
        "health_counts": dict(counters["health"]),
        "quality_gate_counts": dict(counters["quality_gate"]),
        "validation_failed_count": counters["flags"].get("validation_failed", 0),
        "unverified_count": counters["flags"].get("unverified", 0),
        "failed_tool_run_count": counters["flags"].get("failed_tools", 0),
        "model_error_run_count": counters["flags"].get("model_errors", 0),
        "validation_failed_rate": _rate(counters["flags"].get("validation_failed", 0), run_count),
        "unverified_rate": _rate(counters["flags"].get("unverified", 0), run_count),
        "failed_tool_run_rate": _rate(counters["flags"].get("failed_tools", 0), run_count),
        "model_error_run_rate": _rate(counters["flags"].get("model_errors", 0), run_count),
        "top_issue_codes": _top_items(issue_counts),
        "top_quality_gate_checks": _top_items(gate_check_counts),
        "top_failed_tools": _top_items(failed_tool_counts),
        "top_model_errors": _top_items(model_error_counts),
        "top_validation_commands": _top_items(validation_command_counts),
        "test_case_count": sum(test_status_counts.values()),
        "test_status_counts": dict(test_status_counts),
        "top_failed_tests": _top_items(failed_test_counts),
        "slowest_tests": _duration_items(slowest_tests),
        "timing_regressions": _timing_regressions(nodeid_durations),
        "test_duration_trends": _test_duration_trends(nodeid_durations),
        "validation_command_trends": _validation_command_trends(command_durations),
        "recent_problem_runs": _recent_problem_runs(rows),
    }


def format_run_analytics_markdown(analytics: dict[str, Any]) -> str:
    lines = [
        "# Run Analytics",
        "",
        f"- runs: `{analytics.get('run_count') or 0}`",
        f"- validation_failed_rate: `{analytics.get('validation_failed_rate') or 0}`",
        f"- unverified_rate: `{analytics.get('unverified_rate') or 0}`",
        f"- failed_tool_run_rate: `{analytics.get('failed_tool_run_rate') or 0}`",
        f"- model_error_run_rate: `{analytics.get('model_error_run_rate') or 0}`",
        "",
        "## Status",
        "",
    ]
    lines.extend(_counter_lines(analytics.get("status_counts")))
    lines.extend(["", "## Health", ""])
    lines.extend(_counter_lines(analytics.get("health_counts")))
    lines.extend(["", "## Quality Gate", ""])
    lines.extend(_counter_lines(analytics.get("quality_gate_counts")))
    lines.extend(["", "## Top Issue Codes", ""])
    lines.extend(_top_lines(analytics.get("top_issue_codes")))
    lines.extend(["", "## Top Gate Checks", ""])
    lines.extend(_top_lines(analytics.get("top_quality_gate_checks")))
    lines.extend(["", "## Top Failed Tools", ""])
    lines.extend(_top_lines(analytics.get("top_failed_tools")))
    lines.extend(["", "## Top Model Errors", ""])
    lines.extend(_top_lines(analytics.get("top_model_errors")))
    lines.extend(["", "## Top Validation Commands", ""])
    lines.extend(_top_lines(analytics.get("top_validation_commands")))
    lines.extend(["", "## Test Cases", ""])
    lines.append(f"- total: `{analytics.get('test_case_count') or 0}`")
    lines.extend(_counter_lines(analytics.get("test_status_counts")))
    lines.extend(["", "## Top Failed Tests", ""])
    lines.extend(_top_lines(analytics.get("top_failed_tests")))
    lines.extend(["", "## Slowest Tests", ""])
    lines.extend(_duration_lines(analytics.get("slowest_tests")))
    lines.extend(["", "## Timing Regressions", ""])
    lines.extend(_timing_regression_lines(analytics.get("timing_regressions")))
    lines.extend(["", "## Validation Command Trends", ""])
    lines.extend(_validation_command_trend_lines(analytics.get("validation_command_trends")))
    lines.extend(["", "## Recent Problem Runs", ""])
    lines.extend(_problem_run_lines(analytics.get("recent_problem_runs")))
    return "\n".join(lines)


def _base_counters(rows: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    status_counts: Counter[str] = Counter()
    health_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    for row in rows:
        status_counts[str(row.get("status") or "running/unknown")] += 1
        health_counts[str(row.get("health") or "unknown")] += 1
        gate_counts[str(row.get("quality_gate_status") or "unknown")] += 1
        if row.get("validation_failed"):
            flags["validation_failed"] += 1
        if row.get("unverified"):
            flags["unverified"] += 1
        if int(row.get("failed_tool_count") or 0) > 0:
            flags["failed_tools"] += 1
        if _row_has_model_errors(row):
            flags["model_errors"] += 1
    return {"status": status_counts, "health": health_counts, "quality_gate": gate_counts, "flags": flags}


def _row_has_model_errors(row: dict[str, Any]) -> bool:
    events = _safe_read_events(row.get("path"))
    return any(event.get("event") == "model_error" for event in events)


def _safe_read_events(path: Any) -> list[dict[str, Any]]:
    try:
        return read_run_events(str(path))
    except (OSError, ValueError, TypeError):
        return []


def _gate_check_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    finish_data = _last_event_data(events, "run_finish")
    final_trust = finish_data.get("final_trust") if isinstance(finish_data.get("final_trust"), dict) else {}
    gate = final_trust.get("quality_gate") if isinstance(final_trust.get("quality_gate"), dict) else {}
    checks = gate.get("checks") if isinstance(gate.get("checks"), list) else []
    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status") or "unknown")
        code = str(check.get("code") or "unknown")
        if status in {"fail", "warn"}:
            counts[f"{status}:{code}"] += 1
    return counts


def _failed_tool_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "tool_result":
            continue
        data = _event_data(event)
        if _result_ok(data):
            continue
        counts[str(data.get("name") or "unknown")] += 1
    return counts


def _model_error_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "model_error":
            continue
        data = _event_data(event)
        model = str(data.get("model") or "unknown")
        error_type = str(data.get("error_type") or "error")
        counts[f"{model}:{error_type}"] += 1
    return counts


def _validation_command_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "tool_result":
            continue
        data = _event_data(event)
        if data.get("name") != "run_command":
            continue
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        command = normalize_pytest_command(str(args.get("command") or ""))
        if command:
            counts[command] += 1
    return counts


def _test_case_counts(
    events: list[dict[str, Any]],
) -> tuple[Counter[str], Counter[str], dict[str, int], dict[str, dict[str, Any]]]:
    status_counts: Counter[str] = Counter()
    failed_tests: Counter[str] = Counter()
    slowest: dict[str, int] = {}
    durations: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event") != "test_case_result":
            continue
        data = _event_data(event)
        nodeid = str(data.get("nodeid") or "unknown")
        status = str(data.get("status") or "unknown")
        duration_ms = int(data.get("duration_ms") or 0)
        status_counts[status] += 1
        if status in {"failed", "error"}:
            failed_tests[nodeid] += 1
        if duration_ms > slowest.get(nodeid, 0):
            slowest[nodeid] = duration_ms
        prev = durations.get(nodeid)
        if prev is None or duration_ms >= int(prev.get("ms") or 0):
            durations[nodeid] = {"ms": duration_ms, "status": status}
    return status_counts, failed_tests, slowest, durations


def _validation_command_durations(events: list[dict[str, Any]]) -> dict[str, int]:
    durations: dict[str, int] = {}
    for event in events:
        if event.get("event") != "tool_result":
            continue
        data = _event_data(event)
        if data.get("name") != "run_command":
            continue
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        command = normalize_pytest_command(str(args.get("command") or ""))
        if not command:
            continue
        result = data.get("result") if isinstance(data.get("result"), dict) else data
        ms = _event_duration_ms(result)
        if ms is None:
            continue
        durations[command] = max(durations.get(command, 0), ms)
    return durations


def _timing_regressions(
    nodeid_durations: dict[str, list[dict[str, Any]]],
    *,
    limit: int = _TIMING_TOP_LIMIT,
) -> list[dict[str, Any]]:
    regressions: list[dict[str, Any]] = []
    for nodeid, samples in nodeid_durations.items():
        ms_list = _ordered_durations(samples)
        if len(ms_list) < _TIMING_MIN_BASELINE_SAMPLES + 1:
            continue
        current = ms_list[-1]
        window = ms_list[-1 - _TIMING_BASELINE_WINDOW:-1]
        if len(window) < _TIMING_MIN_BASELINE_SAMPLES:
            continue
        baseline = _median(window)
        if baseline <= 0:
            continue
        ratio = current / baseline
        delta = current - int(baseline)
        if ratio >= _TIMING_REGRESSION_RATIO and delta >= _TIMING_MIN_DELTA_MS:
            regressions.append(
                {
                    "nodeid": nodeid,
                    "current_ms": current,
                    "baseline_ms": int(baseline),
                    "ratio": round(ratio, 2),
                    "delta_ms": delta,
                    "samples": len(ms_list),
                    "trend": _duration_trend(ms_list),
                }
            )
    regressions.sort(key=lambda item: (-item["ratio"], -item["delta_ms"], item["nodeid"]))
    return regressions[:limit]


def _test_duration_trends(
    nodeid_durations: dict[str, list[dict[str, Any]]],
    *,
    limit: int = _TIMING_TOP_LIMIT,
) -> list[dict[str, Any]]:
    trends: list[dict[str, Any]] = []
    for nodeid, samples in nodeid_durations.items():
        ms_list = _ordered_durations(samples)
        if len(ms_list) < 2:
            continue
        avg_ms = int(sum(ms_list) / len(ms_list))
        trends.append(
            {
                "nodeid": nodeid,
                "samples": len(ms_list),
                "durations": ms_list[-_TIMING_TREND_SERIES_LIMIT:],
                "avg_ms": avg_ms,
                "recent_ms": ms_list[-1],
                "trend": _duration_trend(ms_list),
            }
        )
    trends.sort(key=lambda item: (-item["samples"], -item["avg_ms"], item["nodeid"]))
    return trends[:limit]


def _validation_command_trends(
    command_durations: dict[str, list[dict[str, Any]]],
    *,
    limit: int = _TIMING_TOP_LIMIT,
) -> list[dict[str, Any]]:
    trends: list[dict[str, Any]] = []
    for command, samples in command_durations.items():
        ms_list = _ordered_durations(samples)
        if not ms_list:
            continue
        avg_ms = int(sum(ms_list) / len(ms_list))
        recent_window = ms_list[-_TIMING_BASELINE_WINDOW:]
        recent_avg = int(sum(recent_window) / len(recent_window)) if recent_window else avg_ms
        trends.append(
            {
                "command": command,
                "samples": len(ms_list),
                "durations": ms_list[-_TIMING_TREND_SERIES_LIMIT:],
                "avg_ms": avg_ms,
                "recent_avg_ms": recent_avg,
                "trend": _duration_trend(ms_list),
            }
        )
    trends.sort(key=lambda item: (-item["samples"], -item["avg_ms"], item["command"]))
    return trends[:limit]


def _ordered_durations(samples: list[dict[str, Any]]) -> list[int]:
    # rows are newest-first, so reverse to oldest-first before taking the tail as "latest".
    ordered = list(reversed(samples))
    return [int(item.get("ms") or 0) for item in ordered if int(item.get("ms") or 0) > 0]


def _median(values: list[int]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return 0.0
    mid = count // 2
    if count % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def _duration_trend(ms_list: list[int]) -> str:
    if len(ms_list) < 4:
        return "unknown"
    mid = len(ms_list) // 2
    old = _median(ms_list[:mid])
    recent = _median(ms_list[mid:])
    if old <= 0:
        return "unknown"
    change = (recent - old) / old
    if change >= _TIMING_TREND_STABLE_RATIO:
        return "slower"
    if change <= -_TIMING_TREND_STABLE_RATIO:
        return "faster"
    return "stable"


def _recent_problem_runs(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        gate = str(row.get("quality_gate_status") or "")
        if (
            row.get("health") in {"fail", "warn"}
            or gate in {"fail", "warn"}
            or row.get("validation_failed")
            or row.get("unverified")
            or int(row.get("failed_tool_count") or 0) > 0
        ):
            selected.append(
                {
                    "run_id": row.get("run_id"),
                    "status": row.get("status"),
                    "health": row.get("health"),
                    "quality_gate_status": row.get("quality_gate_status"),
                    "validation_failed": bool(row.get("validation_failed")),
                    "unverified": bool(row.get("unverified")),
                    "failed_tool_count": int(row.get("failed_tool_count") or 0),
                    "changed_paths": row.get("changed_paths") or [],
                }
            )
        if len(selected) >= limit:
            break
    return selected


def _last_event_data(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for event in reversed(events):
        if event.get("event") == event_type:
            return _event_data(event)
    return {}


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _result_ok(data: dict[str, Any]) -> bool:
    if "ok" in data:
        return bool(data.get("ok"))
    result = data.get("result")
    if isinstance(result, dict):
        if "ok" in result:
            return bool(result.get("ok"))
        if "returncode" in result:
            return int(result.get("returncode") or 0) == 0
    return True


def _event_duration_ms(result: dict[str, Any]) -> int | None:
    value = result.get("duration_ms")
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 3)


def _top_items(counter: Counter[str], limit: int = 8) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def _duration_items(values: dict[str, int], limit: int = 8) -> list[dict[str, Any]]:
    return [
        {"name": name, "duration_ms": duration_ms}
        for name, duration_ms in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _counter_lines(value: Any) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- none"]
    return [f"- `{key}`: {count}" for key, count in sorted(value.items())]


def _top_lines(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- none"]
    return [f"- `{item.get('name')}`: {item.get('count')}" for item in items if isinstance(item, dict)]


def _duration_lines(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- none"]
    return [
        f"- `{item.get('name')}`: {item.get('duration_ms')}ms"
        for item in items
        if isinstance(item, dict)
    ]


def _timing_regression_lines(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('nodeid')}`: {item.get('current_ms')}ms vs baseline {item.get('baseline_ms')}ms "
            f"({item.get('ratio')}x, +{item.get('delta_ms')}ms, {item.get('samples')} samples, {item.get('trend')})"
        )
    return lines


def _validation_command_trend_lines(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('command')}`: avg {item.get('avg_ms')}ms, recent {item.get('recent_avg_ms')}ms "
            f"({item.get('samples')} samples, {item.get('trend')})"
        )
    return lines


def _problem_run_lines(value: Any) -> list[str]:
    rows = value if isinstance(value, list) else []
    if not rows:
        return ["- none"]
    lines: list[str] = []
    for row in rows:
        bits = [
            f"status `{row.get('status') or 'unknown'}`",
            f"health `{row.get('health') or 'unknown'}`",
            f"gate `{row.get('quality_gate_status') or 'unknown'}`",
        ]
        if row.get("validation_failed"):
            bits.append("validation_failed")
        if row.get("unverified"):
            bits.append("unverified")
        failed_tool_count = int(row.get("failed_tool_count") or 0)
        if failed_tool_count:
            bits.append(f"failed_tools `{failed_tool_count}`")
        lines.append(f"- `{str(row.get('run_id') or 'unknown')[:10]}` - " + ", ".join(bits))
    return lines
