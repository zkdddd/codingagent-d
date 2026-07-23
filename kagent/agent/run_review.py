from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .run_log import read_run_events, summarize_run_log
from .run_self_check import analyze_run_health


def build_run_review(run_log_path: str | Path) -> dict[str, Any]:
    events = read_run_events(run_log_path)
    summary = summarize_run_log(run_log_path)
    health = analyze_run_health(run_log_path)
    finish_data = _event_data(_last_event(events, "run_finish"))
    model_requests = _model_requests(events)
    model_errors = _model_errors(events)
    project_rules = _latest_project_rules(events)
    symbol_impacts = _symbol_impacts(summary, events)
    validation_selection = _latest_validation_selection(events)
    risk_flags = _risk_flags(
        summary=summary,
        health=health,
        model_errors=model_errors,
        project_rules=project_rules,
        finish_data=finish_data,
    )

    review = {
        "path": str(Path(run_log_path)),
        "run_id": summary.get("run_id"),
        "status": summary.get("status") or "running/unknown",
        "workspace": summary.get("workspace_root"),
        "task": _task(events),
        "started_at": summary.get("started_at"),
        "finished_at": summary.get("finished_at"),
        "changed_paths": summary.get("changed_paths") or [],
        "validation": {
            "validated": bool(finish_data.get("validated")),
            "failed": bool(summary.get("validation_failed")),
            "last_summary": summary.get("last_validation_summary"),
        },
        "failed_tools": health.get("failed_tools") or [],
        "model_requests": model_requests,
        "model_errors": model_errors,
        "symbol_impacts": symbol_impacts,
        "validation_selection": validation_selection,
        "project_rules": project_rules,
        "health": {
            "status": health.get("health"),
            "trustworthy": bool(health.get("trustworthy")),
            "issues": health.get("issues") or [],
        },
        "risk_flags": risk_flags,
        "recommended_next_steps": _recommended_next_steps(
            risk_flags=risk_flags,
            symbol_impacts=symbol_impacts,
            changed_paths=summary.get("changed_paths") or [],
        ),
    }
    review["quality_gate"] = build_quality_gate(review)
    return review


def format_run_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Run Review",
        "",
        f"- run_id: `{review.get('run_id') or 'unknown'}`",
        f"- status: `{review.get('status') or 'unknown'}`",
        f"- workspace: `{review.get('workspace') or 'unknown'}`",
        f"- task: {_inline(review.get('task') or 'unknown')}",
    ]

    changed_paths = _list(review.get("changed_paths"))
    lines.extend(["", "## Changed Paths"])
    lines.extend(_bullet_lines(changed_paths, empty="none", code=True))

    validation = review.get("validation") if isinstance(review.get("validation"), dict) else {}
    validation_status = "failed" if validation.get("failed") else "passed/recorded"
    if not validation.get("validated") and changed_paths:
        validation_status = "not validated"
    lines.extend(
        [
            "",
            "## Validation",
            f"- status: `{validation_status}`",
            f"- last_summary: {_inline(validation.get('last_summary') or 'none')}",
        ]
    )
    selection_lines = _validation_selection_lines(review.get("validation_selection"))
    if selection_lines:
        lines.extend(["", "### Selection Rationale"])
        lines.extend(selection_lines)

    lines.extend(["", "## Runtime Signals"])
    lines.extend(_bullet_lines(_failed_tool_lines(review.get("failed_tools")), empty="failed_tools: none"))
    lines.extend(_bullet_lines(_model_request_lines(review.get("model_requests")), empty="model_requests: none"))
    lines.extend(_bullet_lines(_model_error_lines(review.get("model_errors")), empty="model_errors: none"))

    project_rules = review.get("project_rules") if isinstance(review.get("project_rules"), dict) else None
    lines.extend(["", "## Project Rules"])
    lines.append(f"- {_project_rules_line(project_rules)}")

    lines.extend(["", "## Symbol Impacts"])
    lines.extend(_bullet_lines(_symbol_impact_lines(review.get("symbol_impacts")), empty="none"))

    lines.extend(["", "## Risks"])
    lines.extend(_bullet_lines(_list(review.get("risk_flags")), empty="none", code=True))

    lines.extend(["", "## Quality Gate"])
    lines.extend(_quality_gate_markdown_lines(review.get("quality_gate")))

    lines.extend(["", "## Recommended Next Steps"])
    lines.extend(_bullet_lines(_list(review.get("recommended_next_steps")), empty="none"))
    return "\n".join(lines)


def build_quality_gate(review: dict[str, Any]) -> dict[str, Any]:
    checks = _quality_gate_checks(review)
    statuses = {str(check.get("status")) for check in checks}
    status = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {
        "status": status,
        "passed": status == "pass",
        "checks": checks,
        "summary": _quality_gate_summary(status, checks),
    }


def format_quality_gate_markdown(review_or_gate: dict[str, Any]) -> str:
    gate = (
        review_or_gate.get("quality_gate")
        if isinstance(review_or_gate.get("quality_gate"), dict)
        else review_or_gate
    )
    lines = ["# Quality Gate", ""]
    lines.extend(_quality_gate_markdown_lines(gate))
    return "\n".join(lines)


def format_bug_report_markdown(review: dict[str, Any]) -> str:
    validation = review.get("validation") if isinstance(review.get("validation"), dict) else {}
    risk_flags = _list(review.get("risk_flags"))
    changed_paths = _list(review.get("changed_paths"))
    failed_tools = _failed_tool_lines(review.get("failed_tools"))
    model_errors = _model_error_lines(review.get("model_errors"))
    symbol_lines = _symbol_impact_lines(review.get("symbol_impacts"))
    issue_title = _bug_report_title(review, risk_flags)

    lines = [
        "# Bug Report",
        "",
        "## Title",
        "",
        f"{issue_title}",
        "",
        "## Context",
        "",
        f"- run_id: `{review.get('run_id') or 'unknown'}`",
        f"- status: `{review.get('status') or 'unknown'}`",
        f"- task: {_inline(review.get('task') or 'unknown')}",
        f"- workspace: `{review.get('workspace') or 'unknown'}`",
        "",
        "## Reproduction Steps",
        "",
        "1. Open the workspace recorded above.",
        f"2. Review the changed paths from run `{review.get('run_id') or 'unknown'}`.",
        "3. Re-run the validation command or scenario listed below.",
        "",
        "## Actual Result",
        "",
    ]
    actual = _actual_result_lines(validation, failed_tools, model_errors, risk_flags)
    lines.extend(_bullet_lines(actual, empty="No failure signal recorded."))
    lines.extend(
        [
            "",
            "## Expected Result",
            "",
            "- Changed code is validated, tool failures are recovered, and no unresolved risk flags remain.",
            "",
            "## Affected Files",
            "",
        ]
    )
    lines.extend(_bullet_lines(changed_paths, empty="none", code=True))
    lines.extend(["", "## Impacted Symbols", ""])
    lines.extend(_bullet_lines(symbol_lines, empty="none"))
    lines.extend(["", "## Suspected Cause", ""])
    lines.extend(_bullet_lines(_suspected_cause_lines(review, risk_flags), empty="Insufficient signal in run log."))
    lines.extend(["", "## Suggested Fix", ""])
    lines.extend(_bullet_lines(_list(review.get("recommended_next_steps")), empty="Review the run manually."))
    lines.extend(["", "## Validation Evidence", ""])
    lines.append(f"- validated: `{bool(validation.get('validated'))}`")
    lines.append(f"- failed: `{bool(validation.get('failed'))}`")
    lines.append(f"- last_summary: {_inline(validation.get('last_summary') or 'none')}")
    return "\n".join(lines)


def format_regression_plan_markdown(review: dict[str, Any]) -> str:
    validation = review.get("validation") if isinstance(review.get("validation"), dict) else {}
    changed_paths = _list(review.get("changed_paths"))
    symbol_impacts = review.get("symbol_impacts") if isinstance(review.get("symbol_impacts"), list) else []
    commands = _regression_commands(symbol_impacts, validation)
    related_tests = _regression_related_tests(symbol_impacts)
    risk_flags = _list(review.get("risk_flags"))

    lines = [
        "# Regression Test Plan",
        "",
        f"- run_id: `{review.get('run_id') or 'unknown'}`",
        f"- task: {_inline(review.get('task') or 'unknown')}",
        f"- validation_summary: {_inline(validation.get('last_summary') or 'none')}",
        "",
        "## Scope",
        "",
    ]
    lines.extend(_bullet_lines(changed_paths, empty="No changed paths recorded.", code=True))
    lines.extend(["", "## Risk Focus", ""])
    lines.extend(_bullet_lines(_regression_risk_focus(review, risk_flags), empty="No specific risk focus recorded."))
    lines.extend(["", "## Related Tests", ""])
    lines.extend(_bullet_lines(related_tests, empty="No related tests found in symbol impacts.", code=True))
    lines.extend(["", "## Commands", ""])
    lines.extend(_bullet_lines(commands, empty="No validation command recorded.", code=True))
    selection_lines = _validation_selection_lines(review.get("validation_selection"))
    if selection_lines:
        lines.extend(["", "## Selection Rationale", ""])
        lines.extend(selection_lines)
    lines.extend(["", "## Manual Checks", ""])
    lines.extend(_bullet_lines(_manual_check_lines(review, risk_flags), empty="No manual checks required from current signals."))
    lines.extend(["", "## Exit Criteria", ""])
    lines.extend(
        [
            "- Focused validation passes for changed files or impacted symbols.",
            "- Full project validation passes when the changed area is shared or high risk.",
            "- Remaining risk flags are either resolved or explicitly documented.",
        ]
    )
    return "\n".join(lines)


def _event_data(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {}
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _last_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    return next((event for event in reversed(events) if event.get("event") == event_type), None)


def _task(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        data = _event_data(event)
        for key in ("task", "user_task", "prompt", "objective"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return _short_text(value, limit=240)
    return None


def _model_requests(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "model_request":
            continue
        data = _event_data(event)
        model = str(data.get("model") or "unknown")
        effort = str(data.get("reasoning_effort") or "no-reasoning")
        fallback = bool(data.get("fallback_without_reasoning"))
        key = f"{model}|{effort}|{fallback}"
        counts[key] += 1

    requests: list[dict[str, Any]] = []
    for key, count in counts.most_common():
        model, effort, fallback = key.split("|", 2)
        requests.append(
            {
                "model": model,
                "reasoning_effort": effort,
                "fallback_without_reasoning": fallback == "True",
                "count": count,
            }
        )
    return requests


def _model_errors(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for event in events:
        if event.get("event") != "model_error":
            continue
        data = _event_data(event)
        errors.append(
            {
                "model": str(data.get("model") or "unknown"),
                "error_type": str(data.get("error_type") or "error"),
                "detail": _short_text(data.get("error")) or "",
            }
        )
    return errors


def _latest_project_rules(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("event") != "project_rules_check":
            continue
        data = _event_data(event)
        return {
            "path": data.get("path"),
            "health": data.get("health"),
            "score": data.get("score"),
            "issue_count": data.get("issue_count"),
            "issues": data.get("issues") if isinstance(data.get("issues"), list) else [],
        }
    return None


def _latest_validation_selection(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        data = _event_data(event)
        selection = None
        if event.get("event") == "validation_plan":
            result = data.get("result") if isinstance(data.get("result"), dict) else data
            selection = result.get("selection") if isinstance(result.get("selection"), dict) else None
        elif event.get("event") == "tool_result" and data.get("name") == "validation_plan":
            result = data.get("result") if isinstance(data.get("result"), dict) else {}
            selection = result.get("selection") if isinstance(result.get("selection"), dict) else None
        if not selection:
            continue
        tiers = selection.get("tiers") if isinstance(selection.get("tiers"), list) else []
        return {
            "strategy": selection.get("strategy"),
            "changed_paths": _list(selection.get("changed_paths")),
            "tiers": [item for item in tiers if isinstance(item, dict)][:12],
        }
    return None


def _symbol_impacts(summary: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    impacts: list[dict[str, Any]] = []
    raw_summary_impacts = summary.get("symbol_impacts")
    if isinstance(raw_summary_impacts, list):
        impacts.extend(item for item in raw_summary_impacts if isinstance(item, dict))

    for event in events:
        data = _event_data(event)
        impacts.extend(_nested_symbol_impacts(data))

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for impact in impacts:
        symbol = str(impact.get("symbol") or "unknown")
        definition_path = str(impact.get("definition_path") or impact.get("path") or "unknown")
        key = (symbol, definition_path)
        normalized = {
            "symbol": symbol,
            "definition_path": definition_path,
            "reference_count": impact.get("reference_count"),
            "related_tests": _list(impact.get("related_tests"))[:5],
            "validation_commands": _commands(impact.get("validation_commands"))[:5],
        }
        if key not in by_key:
            by_key[key] = normalized
            continue
        existing = by_key[key]
        existing["reference_count"] = existing.get("reference_count") or normalized.get("reference_count")
        existing["related_tests"] = _merge_unique(
            _list(existing.get("related_tests")), normalized["related_tests"], limit=5
        )
        existing["validation_commands"] = _merge_unique(
            _list(existing.get("validation_commands")), normalized["validation_commands"], limit=5
        )
    return list(by_key.values())[:12]


def _nested_symbol_impacts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        raw = value.get("symbol_impacts")
        found = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        for child in value.values():
            if isinstance(child, dict | list):
                found.extend(_nested_symbol_impacts(child))
        return found
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict | list):
                items.extend(_nested_symbol_impacts(item))
        return items
    return []


def _risk_flags(
    *,
    summary: dict[str, Any],
    health: dict[str, Any],
    model_errors: list[dict[str, str]],
    project_rules: dict[str, Any] | None,
    finish_data: dict[str, Any],
) -> list[str]:
    flags = [str(issue.get("code")) for issue in health.get("issues") or [] if issue.get("code")]
    changed_paths = summary.get("changed_paths") or []
    if changed_paths and not finish_data.get("validated") and "unverified_changes" not in flags:
        flags.append("unverified_changes")
    if model_errors:
        flags.append("model_errors")
    if project_rules is None:
        flags.append("project_rules_not_checked")
    elif str(project_rules.get("health") or "").lower() not in {"", "pass", "healthy", "ok", "good"}:
        flags.append("project_rules_need_attention")
    return list(dict.fromkeys(flags))


def _recommended_next_steps(
    *, risk_flags: list[str], symbol_impacts: list[dict[str, Any]], changed_paths: list[str]
) -> list[str]:
    steps: list[str] = []
    if "validation_failed" in risk_flags:
        steps.append("Inspect the last validation failure, fix the root cause, then rerun focused validation.")
    if "unverified_changes" in risk_flags:
        steps.append("Run the narrowest relevant validation for the changed files before finalizing.")
    if "failed_tools" in risk_flags:
        steps.append("Review failed tool results and confirm they were recovered or are no longer relevant.")
    if "model_errors" in risk_flags:
        steps.append("Check model settings or fallback behavior before relying on this run.")
    if "project_rules_not_checked" in risk_flags:
        steps.append("Run a project rules check so local validation, safety, and workflow rules are visible.")
    if "project_rules_need_attention" in risk_flags:
        steps.append("Update or follow the issues reported by KAGENT.md project rules.")
    if symbol_impacts:
        steps.append("Prioritize review and tests around impacted symbols and their related tests.")
    if changed_paths and not steps:
        steps.append("Review the changed files and keep the recorded validation summary with the final answer.")
    if not steps:
        steps.append("No immediate follow-up detected from the run log.")
    return list(dict.fromkeys(steps))


def _quality_gate_checks(review: dict[str, Any]) -> list[dict[str, str]]:
    validation = review.get("validation") if isinstance(review.get("validation"), dict) else {}
    changed_paths = _list(review.get("changed_paths"))
    risk_flags = set(_list(review.get("risk_flags")))
    failed_tools = review.get("failed_tools") if isinstance(review.get("failed_tools"), list) else []
    model_errors = review.get("model_errors") if isinstance(review.get("model_errors"), list) else []
    project_rules = review.get("project_rules") if isinstance(review.get("project_rules"), dict) else None
    symbol_impacts = review.get("symbol_impacts") if isinstance(review.get("symbol_impacts"), list) else []

    checks = [
        _gate_check(
            "run_completed",
            "pass" if str(review.get("status") or "") == "completed" else "fail",
            f"Run status is `{review.get('status') or 'unknown'}`.",
        ),
        _gate_check(
            "changes_validated",
            "pass" if not changed_paths or validation.get("validated") else "fail",
            "Changed paths were validated." if validation.get("validated") else "Changed paths lack successful validation.",
        ),
        _gate_check(
            "validation_passed",
            "fail" if validation.get("failed") else "pass",
            _short_text(validation.get("last_summary")) or "No validation failure recorded.",
        ),
        _gate_check(
            "tool_failures_recovered",
            "warn" if failed_tools else "pass",
            f"{len(failed_tools)} failed tool group(s) recorded." if failed_tools else "No failed tool groups recorded.",
        ),
        _gate_check(
            "model_errors_absent",
            "warn" if model_errors else "pass",
            f"{len(model_errors)} model error(s) recorded." if model_errors else "No model errors recorded.",
        ),
    ]

    if project_rules is None:
        checks.append(
            _gate_check(
                "project_rules_checked",
                "warn",
                "`KAGENT.md` project rules were not checked.",
            )
        )
    else:
        healthy = str(project_rules.get("health") or "").lower() in {"pass", "healthy", "ok", "good"}
        checks.append(
            _gate_check(
                "project_rules_healthy",
                "warn" if not healthy else "pass",
                _project_rules_line(project_rules),
            )
        )

    if changed_paths and not symbol_impacts:
        checks.append(
            _gate_check(
                "symbol_impact_present",
                "warn",
                "Changed paths exist but no symbol impact summary was recorded.",
            )
        )
    elif symbol_impacts:
        checks.append(
            _gate_check(
                "symbol_impact_present",
                "pass",
                f"{len(symbol_impacts)} impacted symbol(s) recorded.",
            )
        )

    if "unverified_changes" in risk_flags:
        checks.append(_gate_check("risk_unverified_changes", "fail", "Unverified changes remain in risk flags."))
    if "validation_failed" in risk_flags:
        checks.append(_gate_check("risk_validation_failed", "fail", "Validation failure remains in risk flags."))
    return checks


def _gate_check(code: str, status: str, message: str) -> dict[str, str]:
    return {"code": code, "status": status, "message": message}


def _quality_gate_summary(status: str, checks: list[dict[str, str]]) -> str:
    counts = Counter(str(check.get("status") or "unknown") for check in checks)
    return f"{status}: {counts.get('fail', 0)} fail, {counts.get('warn', 0)} warn, {counts.get('pass', 0)} pass"


def _quality_gate_markdown_lines(gate: Any) -> list[str]:
    if not isinstance(gate, dict):
        return ["- status: `unknown`", "- summary: `quality gate unavailable`"]
    lines = [
        f"- status: `{gate.get('status') or 'unknown'}`",
        f"- passed: `{bool(gate.get('passed'))}`",
        f"- summary: {_inline(gate.get('summary') or 'none')}",
        "",
        "## Checks",
        "",
    ]
    checks = gate.get("checks") if isinstance(gate.get("checks"), list) else []
    if not checks:
        lines.append("- none")
        return lines
    for check in checks:
        if not isinstance(check, dict):
            continue
        lines.append(
            f"- [{check.get('status') or 'unknown'}] `{check.get('code') or 'unknown'}`: "
            f"{check.get('message') or ''}"
        )
    return lines


def _validation_selection_lines(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    lines: list[str] = []
    strategy = _short_text(value.get("strategy"), limit=220)
    if strategy:
        lines.append(f"- strategy: {strategy}")
    tiers = value.get("tiers") if isinstance(value.get("tiers"), list) else []
    for tier in tiers[:8]:
        if not isinstance(tier, dict):
            continue
        command = str(tier.get("command") or "").strip()
        if not command:
            continue
        parts = [
            f"tier `{tier.get('tier') or 'other'}`",
            f"label `{tier.get('label') or 'unknown'}`",
        ]
        if tier.get("selection_score") is not None:
            parts.append(f"score `{tier.get('selection_score')}`")
        if tier.get("success_rate") is not None:
            parts.append(f"success `{tier.get('success_rate')}`")
        if tier.get("failure_rate") is not None:
            parts.append(f"failure `{tier.get('failure_rate')}`")
        if tier.get("avg_duration_ms") is not None:
            parts.append(f"avg `{tier.get('avg_duration_ms')}ms`")
        if tier.get("symbol"):
            parts.append(f"symbol `{tier.get('symbol')}`")
        if tier.get("related_test"):
            parts.append(f"test `{tier.get('related_test')}`")
        reason = _short_text(tier.get("reason"), limit=180)
        if reason:
            parts.append(f"reason {reason}")
        lines.append(f"- `{command}` - " + ", ".join(parts))
    return lines


def _failed_tool_lines(value: Any) -> list[str]:
    tools = value if isinstance(value, list) else []
    lines: list[str] = []
    for item in tools:
        if not isinstance(item, dict):
            continue
        detail = f": {item.get('detail')}" if item.get("detail") else ""
        lines.append(f"failed_tool: `{item.get('name') or 'unknown'}` x{item.get('count') or 1}{detail}")
    return lines


def _model_request_lines(value: Any) -> list[str]:
    requests = value if isinstance(value, list) else []
    lines: list[str] = []
    for item in requests:
        if not isinstance(item, dict):
            continue
        fallback = " fallback" if item.get("fallback_without_reasoning") else ""
        lines.append(
            f"model_request: `{item.get('model') or 'unknown'}`/"
            f"`{item.get('reasoning_effort') or 'no-reasoning'}` x{item.get('count') or 1}{fallback}"
        )
    return lines


def _model_error_lines(value: Any) -> list[str]:
    errors = value if isinstance(value, list) else []
    lines: list[str] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        detail = f": {item.get('detail')}" if item.get("detail") else ""
        lines.append(f"model_error: `{item.get('model') or 'unknown'}` {item.get('error_type') or 'error'}{detail}")
    return lines


def _bug_report_title(review: dict[str, Any], risk_flags: list[str]) -> str:
    task = _short_text(review.get("task"), limit=80) or "Agent run"
    if "validation_failed" in risk_flags:
        return f"Validation failure after: {task}"
    if "unverified_changes" in risk_flags:
        return f"Unverified code changes after: {task}"
    if "failed_tools" in risk_flags:
        return f"Tool failure during: {task}"
    if "model_errors" in risk_flags:
        return f"Model error during: {task}"
    return f"Review follow-up for: {task}"


def _actual_result_lines(
    validation: dict[str, Any], failed_tools: list[str], model_errors: list[str], risk_flags: list[str]
) -> list[str]:
    lines: list[str] = []
    if validation.get("failed"):
        lines.append(f"Validation failed: {_short_text(validation.get('last_summary')) or 'no summary'}")
    if not validation.get("validated"):
        lines.append("The run did not record successful validation.")
    lines.extend(failed_tools)
    lines.extend(model_errors)
    lines.extend(f"risk_flag: `{flag}`" for flag in risk_flags)
    return lines


def _suspected_cause_lines(review: dict[str, Any], risk_flags: list[str]) -> list[str]:
    lines: list[str] = []
    validation = review.get("validation") if isinstance(review.get("validation"), dict) else {}
    if "validation_failed" in risk_flags:
        lines.append(f"Last validation result points to: {_short_text(validation.get('last_summary')) or 'unknown failure'}")
    if "failed_tools" in risk_flags:
        lines.append("One or more tool calls failed and may have left the task incomplete.")
    if "model_errors" in risk_flags:
        lines.append("Model request errors or fallback behavior occurred during the run.")
    if "project_rules_need_attention" in risk_flags:
        lines.append("Project rules were checked but reported missing or weak workflow guidance.")
    if "project_rules_not_checked" in risk_flags:
        lines.append("Project rules were not checked, so local workflow constraints may be missing from the run.")
    for impact in review.get("symbol_impacts") or []:
        if isinstance(impact, dict) and impact.get("symbol"):
            lines.append(
                f"Impacted symbol `{impact.get('symbol')}` should be reviewed at `{impact.get('definition_path') or 'unknown'}`."
            )
    return lines


def _regression_commands(symbol_impacts: list[Any], validation: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for impact in symbol_impacts:
        if isinstance(impact, dict):
            commands = _merge_unique(commands, _commands(impact.get("validation_commands")), limit=10)
    last_summary = str(validation.get("last_summary") or "").strip()
    if last_summary and not commands:
        commands.append(f"Re-run validation that produced: {last_summary}")
    return commands


def _regression_related_tests(symbol_impacts: list[Any]) -> list[str]:
    tests: list[str] = []
    for impact in symbol_impacts:
        if isinstance(impact, dict):
            tests = _merge_unique(tests, _list(impact.get("related_tests")), limit=12)
    return tests


def _regression_risk_focus(review: dict[str, Any], risk_flags: list[str]) -> list[str]:
    lines = [f"risk_flag: `{flag}`" for flag in risk_flags]
    for impact in review.get("symbol_impacts") or []:
        if not isinstance(impact, dict):
            continue
        symbol = impact.get("symbol")
        definition = impact.get("definition_path") or "unknown"
        refs = impact.get("reference_count")
        if symbol:
            detail = f"Impacted symbol `{symbol}` at `{definition}`"
            if refs is not None:
                detail += f" with `{refs}` reference(s)"
            lines.append(detail)
    return lines


def _manual_check_lines(review: dict[str, Any], risk_flags: list[str]) -> list[str]:
    lines: list[str] = []
    if "project_rules_need_attention" in risk_flags or "project_rules_not_checked" in risk_flags:
        lines.append("Confirm `KAGENT.md` rules are present, healthy, and reflected in the run.")
    if "model_errors" in risk_flags:
        lines.append("Confirm the selected model and reasoning settings match the expected runtime metadata.")
    if _list(review.get("changed_paths")) and not (review.get("validation") or {}).get("validated"):
        lines.append("Inspect changed files manually before trusting the result.")
    return lines


def _project_rules_line(project_rules: dict[str, Any] | None) -> str:
    if not project_rules:
        return "not checked"
    parts = [f"health: `{project_rules.get('health') or 'unknown'}`"]
    if project_rules.get("score") is not None:
        parts.append(f"score: `{project_rules.get('score')}`")
    if project_rules.get("issue_count") is not None:
        parts.append(f"issues: `{project_rules.get('issue_count')}`")
    return ", ".join(parts)


def _symbol_impact_lines(value: Any) -> list[str]:
    impacts = value if isinstance(value, list) else []
    lines: list[str] = []
    for impact in impacts:
        if not isinstance(impact, dict):
            continue
        refs = impact.get("reference_count")
        ref_text = f", refs: `{refs}`" if refs is not None else ""
        tests = _list(impact.get("related_tests"))
        test_text = f", tests: {', '.join(f'`{test}`' for test in tests[:3])}" if tests else ""
        lines.append(
            f"`{impact.get('symbol') or 'unknown'}` at "
            f"`{impact.get('definition_path') or 'unknown'}`{ref_text}{test_text}"
        )
    return lines


def _bullet_lines(items: list[str], *, empty: str, code: bool = False) -> list[str]:
    if not items:
        return [f"- {empty}"]
    if code:
        return [f"- `{item}`" for item in items]
    return [f"- {item}" for item in items]


def _commands(value: Any) -> list[str]:
    commands: list[str] = []
    if not isinstance(value, list):
        return commands
    for item in value:
        if isinstance(item, str):
            commands.append(item)
        elif isinstance(item, dict) and item.get("command"):
            commands.append(str(item["command"]))
    return commands


def _list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _merge_unique(first: list[str], second: list[str], *, limit: int) -> list[str]:
    return list(dict.fromkeys([*first, *second]))[:limit]


def _inline(value: Any) -> str:
    text = _short_text(value) or ""
    return f"`{text}`" if text else "`none`"


def _short_text(value: Any, limit: int = 180) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
