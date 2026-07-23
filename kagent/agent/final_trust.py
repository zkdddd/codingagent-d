from __future__ import annotations

from typing import Any


def build_final_trust_summary(
    *,
    status: str,
    content_changed: bool,
    changed_paths: list[str],
    validated: bool,
    validation_failed: bool,
    last_validation_summary: str | None = None,
    failed_tool_count: int = 0,
    loop_warning_count: int = 0,
    symbol_impacts: list[dict[str, Any]] | None = None,
    coverage_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if status != "completed":
        issues.append(
            {
                "severity": "fail",
                "code": "run_not_completed",
                "message": f"Run finished with status `{status}`.",
            }
        )
    if content_changed and changed_paths and not validated:
        issues.append(
            {
                "severity": "fail",
                "code": "unverified_changes",
                "message": "Workspace files changed, but validation did not run or did not complete.",
            }
        )
    if validation_failed:
        issues.append(
            {
                "severity": "fail",
                "code": "validation_failed",
                "message": last_validation_summary or "Validation failed.",
            }
        )
    if failed_tool_count > 0:
        issues.append(
            {
                "severity": "warn",
                "code": "failed_tools",
                "message": f"{failed_tool_count} tool call(s) failed during the run.",
            }
        )
    if loop_warning_count > 0:
        issues.append(
            {
                "severity": "warn",
                "code": "loop_warning",
                "message": f"{loop_warning_count} loop warning(s) were emitted.",
            }
        )

    severities = {issue["severity"] for issue in issues}
    health = "fail" if "fail" in severities else "warn" if "warn" in severities else "pass"
    quality_gate = build_quality_gate_summary(
        {
            "health": health,
            "trustworthy": health == "pass",
            "validated": validated,
            "validation_failed": validation_failed,
            "status": status,
            "issues": issues,
            "changed_paths": changed_paths,
            "coverage_gate": coverage_gate,
        }
    )
    return {
        "health": health,
        "trustworthy": health == "pass",
        "status": status,
        "changed_paths": changed_paths,
        "validated": validated,
        "validation_failed": validation_failed,
        "failed_tool_count": failed_tool_count,
        "loop_warning_count": loop_warning_count,
        "symbol_impacts": symbol_impacts or [],
        "issues": issues,
        "quality_gate": quality_gate,
    }


def build_quality_gate_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Runtime quality gate. Check codes are aligned with run_review's
    build_quality_gate (run_completed / changes_validated / validation_passed /
    tool_failures_recovered / coverage_regression + per-issue checks) so the
    gate shown in run history / run_analytics trends matches the richer
    post-hoc review gate in naming and meaning.
    """
    issues = summary.get("issues") if isinstance(summary.get("issues"), list) else []
    status = str(summary.get("status") or "unknown")
    validated = bool(summary.get("validated"))
    validation_failed = bool(summary.get("validation_failed"))
    changed_paths = summary.get("changed_paths") if isinstance(summary.get("changed_paths"), list) else []
    failed_tool_count = int(summary.get("failed_tool_count") or 0)

    checks: list[dict[str, str]] = [
        {
            "code": "run_completed",
            "status": "pass" if status == "completed" else "fail",
            "message": f"Run status is `{status}`.",
        },
        {
            "code": "changes_validated",
            "status": "pass" if not changed_paths or validated else "fail",
            "message": "Changed paths were validated." if validated else "Changed paths lack successful validation.",
        },
        {
            "code": "validation_passed",
            "status": "fail" if validation_failed else "pass",
            "message": "Validation failure remains recorded." if validation_failed else "No validation failure recorded.",
        },
        {
            "code": "tool_failures_recovered",
            "status": "warn" if failed_tool_count else "pass",
            "message": f"{failed_tool_count} failed tool group(s) recorded." if failed_tool_count else "No failed tool groups recorded.",
        },
    ]

    coverage_gate = summary.get("coverage_gate") if isinstance(summary.get("coverage_gate"), dict) else None
    if coverage_gate and str(coverage_gate.get("status") or "") == "warn":
        checks.append(
            {
                "code": "coverage_regression",
                "status": "warn",
                "message": str(coverage_gate.get("message") or "Coverage regression detected."),
            }
        )

    for issue in issues:
        severity = str(issue.get("severity") or "unknown")
        code = str(issue.get("code") or "issue")
        if code in {"run_not_completed", "unverified_changes", "validation_failed", "failed_tools", "loop_warning"}:
            # Already represented by the aligned checks above; avoid duplicate rows.
            continue
        checks.append(
            {
                "code": code,
                "status": "fail" if severity == "fail" else "warn",
                "message": str(issue.get("message") or ""),
            }
        )

    severities = {str(check["status"]) for check in checks}
    gate_status = "fail" if "fail" in severities else "warn" if "warn" in severities else "pass"
    return {
        "status": gate_status,
        "passed": gate_status == "pass",
        "checks": checks,
        "summary": f"{gate_status}: {sum(1 for check in checks if check['status'] == 'fail')} fail, "
        f"{sum(1 for check in checks if check['status'] == 'warn')} warn, "
        f"{sum(1 for check in checks if check['status'] == 'pass')} pass",
    }


def final_trust_prompt(summary: dict[str, Any]) -> str:
    issues = summary.get("issues") if isinstance(summary.get("issues"), list) else []
    gate = summary.get("quality_gate") if isinstance(summary.get("quality_gate"), dict) else None
    lines = [
        "Final response trust check.",
        f"- health: {summary.get('health')}",
        f"- trustworthy: {'yes' if summary.get('trustworthy') else 'no'}",
        f"- validated: {'yes' if summary.get('validated') else 'no'}",
        f"- validation_failed: {'yes' if summary.get('validation_failed') else 'no'}",
    ]
    changed_paths = summary.get("changed_paths") if isinstance(summary.get("changed_paths"), list) else []
    if changed_paths:
        lines.append("- changed_paths: " + ", ".join(str(path) for path in changed_paths[:12]))
    symbol_impacts = summary.get("symbol_impacts") if isinstance(summary.get("symbol_impacts"), list) else []
    if symbol_impacts:
        lines.append("- symbol_impacts:")
        for impact in symbol_impacts[:5]:
            if not isinstance(impact, dict):
                continue
            symbol = impact.get("symbol") or "unknown"
            definition = impact.get("definition_path") or "unknown"
            refs = impact.get("reference_count")
            tests = impact.get("related_tests") if isinstance(impact.get("related_tests"), list) else []
            parts = [f"{symbol} at {definition}"]
            if refs is not None:
                parts.append(f"{refs} reference(s)")
            if tests:
                parts.append("tests: " + ", ".join(str(test) for test in tests[:4]))
            lines.append("- " + "; ".join(parts))
    if issues:
        lines.append("- required_disclosures:")
        for issue in issues:
            lines.append(f"  - [{issue['severity']}] {issue['code']}: {issue['message']}")
    else:
        lines.append("- required_disclosures: none")
    if gate:
        lines.append("- quality_gate:")
        lines.append(f"  - status: {gate.get('status')}")
        lines.append(f"  - passed: {'yes' if gate.get('passed') else 'no'}")
        lines.append(f"  - summary: {gate.get('summary')}")
    lines.append(
        "In the final answer, explicitly mention any fail issue. Mention warn issues briefly as residual risk. "
        "Include the quality gate result. Do not claim validation passed unless validated=yes and validation_failed=no."
    )
    return "\n".join(lines)
