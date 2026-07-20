from kagent.agent.run_log import RunLogger
from kagent.agent.run_review import (
    build_quality_gate,
    build_run_review,
    format_bug_report_markdown,
    format_quality_gate_markdown,
    format_regression_plan_markdown,
    format_run_review_markdown,
)


def test_build_run_review_summarizes_clean_run(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("run_context", {"task": "Add run review core"})
    logger.write("model_request", {"model": "gpt-5.5", "reasoning_effort": "high"})
    logger.write(
        "tool_result",
        {
            "name": "validation_plan",
            "result": {
                "selection": {
                    "strategy": "Run fast syntax checks first, then learned validation.",
                    "changed_paths": ["kagent/agent/run_review.py"],
                    "tiers": [
                        {
                            "tier": "syntax",
                            "label": "Python syntax check",
                            "command": "python -m py_compile kagent/agent/run_review.py",
                            "reason": "Compile changed Python files.",
                            "selection_score": 0.824,
                        },
                        {
                            "tier": "learned",
                            "label": "Learned validation",
                            "command": "python -m pytest -q tests/test_run_review.py",
                            "reason": "Learned from history.",
                            "success_rate": 1.0,
                            "failure_rate": 0.0,
                            "avg_duration_ms": 900,
                            "selection_score": 1.04,
                        },
                    ],
                }
            },
            "ok": True,
        },
    )
    logger.write(
        "project_rules_check",
        {
            "path": "KAGENT.md",
            "health": "good",
            "score": 100,
            "issue_count": 0,
            "issues": [],
        },
    )
    logger.finish(
        "completed",
        {
            "validated": True,
            "validation_failed": False,
            "changed_paths": ["kagent/agent/run_review.py"],
            "last_validation_summary": "199 passed",
        },
    )

    review = build_run_review(logger.path)
    markdown = format_run_review_markdown(review)

    assert review["run_id"] == logger.run_id
    assert review["status"] == "completed"
    assert review["workspace"] == str(tmp_path)
    assert review["task"] == "Add run review core"
    assert review["validation"]["validated"] is True
    assert review["validation"]["failed"] is False
    assert review["validation"]["last_summary"] == "199 passed"
    assert review["changed_paths"] == ["kagent/agent/run_review.py"]
    assert review["model_requests"] == [
        {
            "model": "gpt-5.5",
            "reasoning_effort": "high",
            "fallback_without_reasoning": False,
            "count": 1,
        }
    ]
    assert review["project_rules"]["health"] == "good"
    assert review["validation_selection"]["strategy"].startswith("Run fast syntax checks")
    assert review["validation_selection"]["tiers"][1]["tier"] == "learned"
    assert review["risk_flags"] == []
    assert review["quality_gate"]["status"] == "warn"
    assert any(check["code"] == "symbol_impact_present" for check in review["quality_gate"]["checks"])
    assert review["recommended_next_steps"] == [
        "Review the changed files and keep the recorded validation summary with the final answer."
    ]
    assert "# Run Review" in markdown
    assert "status: `passed/recorded`" in markdown
    assert "Selection Rationale" in markdown
    assert "success `1.0`" in markdown
    assert "avg `900ms`" in markdown
    assert "`kagent/agent/run_review.py`" in markdown


def test_build_run_review_reports_risks_and_symbol_impacts(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("run_context", {"user_task": "Fix validation failure"})
    logger.write(
        "change_plan",
        {
            "plan": {
                "operation": "patch",
                "symbol_impacts": [
                    {
                        "symbol": "build_run_review",
                        "definition_path": "kagent/agent/run_review.py",
                        "reference_count": 2,
                        "related_tests": ["tests/test_run_review.py"],
                        "validation_commands": [
                            {"command": "python -m pytest -q tests/test_run_review.py"}
                        ],
                    }
                ],
            }
        },
    )
    logger.write("model_request", {"model": "gpt-5.5", "reasoning_effort": "high"})
    logger.write(
        "model_error",
        {
            "model": "gpt-5.5",
            "error_type": "ValueError",
            "error": "unsupported parameter: reasoning_effort",
        },
    )
    logger.write(
        "model_request",
        {
            "model": "gpt-5.5",
            "reasoning_effort": None,
            "fallback_without_reasoning": True,
        },
    )
    logger.write("tool_result", {"name": "run_command", "ok": False, "error": "pytest failed"})
    logger.write(
        "project_rules_check",
        {
            "path": "KAGENT.md",
            "health": "weak",
            "score": 40,
            "issue_count": 2,
            "issues": [{"kind": "missing_validation_command", "severity": "high"}],
        },
    )
    logger.finish(
        "completed",
        {
            "validated": True,
            "validation_failed": True,
            "changed_paths": ["kagent/agent/run_review.py"],
            "last_validation_summary": "1 failed",
            "symbol_impacts": [
                {
                    "symbol": "build_run_review",
                    "definition_path": "kagent/agent/run_review.py",
                    "reference_count": 2,
                    "related_tests": ["tests/test_run_review.py"],
                }
            ],
        },
    )

    review = build_run_review(logger.path)
    markdown = format_run_review_markdown(review)

    assert review["task"] == "Fix validation failure"
    assert review["failed_tools"] == [{"name": "run_command", "count": "1", "detail": "pytest failed"}]
    assert review["model_errors"] == [
        {
            "model": "gpt-5.5",
            "error_type": "ValueError",
            "detail": "unsupported parameter: reasoning_effort",
        }
    ]
    assert review["model_requests"][0]["count"] == 1
    assert review["symbol_impacts"] == [
        {
            "symbol": "build_run_review",
            "definition_path": "kagent/agent/run_review.py",
            "reference_count": 2,
            "related_tests": ["tests/test_run_review.py"],
            "validation_commands": ["python -m pytest -q tests/test_run_review.py"],
        }
    ]
    assert review["project_rules"]["health"] == "weak"
    assert review["quality_gate"]["status"] == "fail"
    assert review["quality_gate"]["passed"] is False
    assert review["risk_flags"] == [
        "validation_failed",
        "failed_tools",
        "model_errors",
        "project_rules_need_attention",
    ]
    assert review["recommended_next_steps"][0].startswith("Inspect the last validation failure")
    assert any(
        "Prioritize review and tests around impacted symbols" in step
        for step in review["recommended_next_steps"]
    )
    assert "model_error: `gpt-5.5` ValueError" in markdown
    assert "`build_run_review` at `kagent/agent/run_review.py`" in markdown
    assert "`validation_failed`" in markdown


def test_build_run_review_flags_unfinished_run_without_rules_check(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))

    review = build_run_review(logger.path)

    assert review["status"] == "running/unknown"
    assert review["quality_gate"]["status"] == "fail"
    assert review["risk_flags"] == ["run_not_finished", "project_rules_not_checked"]
    assert review["recommended_next_steps"] == [
        "Run a project rules check so local validation, safety, and workflow rules are visible."
    ]


def test_bug_report_and_regression_plan_use_review_payload(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("run_context", {"task": "Fix validation failure"})
    logger.write(
        "change_plan",
        {
            "plan": {
                "operation": "patch",
                "symbol_impacts": [
                    {
                        "symbol": "build_run_review",
                        "definition_path": "kagent/agent/run_review.py",
                        "reference_count": 2,
                        "related_tests": ["tests/test_run_review.py"],
                        "validation_commands": [
                            {"command": "python -m pytest -q tests/test_run_review.py"}
                        ],
                    }
                ],
            }
        },
    )
    logger.write("tool_result", {"name": "run_command", "ok": False, "error": "pytest failed"})
    logger.write(
        "tool_result",
        {
            "name": "validation_plan",
            "result": {
                "selection": {
                    "strategy": "Use symbol related tests first.",
                    "tiers": [
                        {
                            "tier": "symbol_related_tests",
                            "label": "Related symbol test",
                            "command": "python -m pytest -q tests/test_run_review.py",
                            "reason": "Symbol impact selected this test.",
                            "symbol": "build_run_review",
                            "related_test": "tests/test_run_review.py",
                            "selection_score": 0.92,
                        }
                    ],
                }
            },
            "ok": True,
        },
    )
    logger.write("model_error", {"model": "gpt-5.5", "error_type": "ValueError", "error": "bad args"})
    logger.write(
        "project_rules_check",
        {
            "path": "KAGENT.md",
            "health": "weak",
            "score": 40,
            "issue_count": 2,
            "issues": [{"kind": "missing_validation_command", "severity": "high"}],
        },
    )
    logger.finish(
        "completed",
        {
            "validated": False,
            "validation_failed": True,
            "changed_paths": ["kagent/agent/run_review.py"],
            "last_validation_summary": "1 failed",
            "symbol_impacts": [
                {
                    "symbol": "build_run_review",
                    "definition_path": "kagent/agent/run_review.py",
                    "reference_count": 2,
                    "related_tests": ["tests/test_run_review.py"],
                    "validation_commands": ["python -m pytest -q tests/test_run_review.py"],
                }
            ],
        },
    )

    review = build_run_review(logger.path)
    bug = format_bug_report_markdown(review)
    plan = format_regression_plan_markdown(review)

    assert "# Bug Report" in bug
    assert "Validation failure after: Fix validation failure" in bug
    assert "1 failed" in bug
    assert "`kagent/agent/run_review.py`" in bug
    assert "## Suggested Fix" in bug

    assert "# Regression Test Plan" in plan
    assert "`tests/test_run_review.py`" in plan
    assert "`python -m pytest -q tests/test_run_review.py`" in plan
    assert "risk_flag: `validation_failed`" in plan
    assert "Selection Rationale" in plan
    assert "symbol `build_run_review`" in plan


def test_quality_gate_formats_pass_and_fail_states():
    passing = {
        "status": "completed",
        "changed_paths": [],
        "validation": {"validated": False, "failed": False},
        "failed_tools": [],
        "model_errors": [],
        "project_rules": {"health": "good", "score": 100, "issue_count": 0},
        "symbol_impacts": [],
        "risk_flags": [],
    }
    failing = {
        "status": "completed",
        "changed_paths": ["kagent/app.py"],
        "validation": {"validated": False, "failed": True, "last_summary": "1 failed"},
        "failed_tools": [{"name": "run_command"}],
        "model_errors": [],
        "project_rules": None,
        "symbol_impacts": [],
        "risk_flags": ["unverified_changes", "validation_failed"],
    }

    pass_gate = build_quality_gate(passing)
    fail_gate = build_quality_gate(failing)
    markdown = format_quality_gate_markdown(fail_gate)

    assert pass_gate["status"] == "pass"
    assert pass_gate["passed"] is True
    assert fail_gate["status"] == "fail"
    assert fail_gate["passed"] is False
    assert [check["code"] for check in fail_gate["checks"] if check["status"] == "fail"] == [
        "changes_validated",
        "validation_passed",
        "risk_unverified_changes",
        "risk_validation_failed",
    ]
    assert "# Quality Gate" in markdown
    assert "[fail] `changes_validated`" in markdown
