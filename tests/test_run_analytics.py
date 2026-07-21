from kagent.agent.run_analytics import build_run_analytics, format_run_analytics_markdown
from kagent.agent.run_log import RunLogger


def test_build_run_analytics_summarizes_failure_trends(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path))

    clean = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    clean.finish(
        "completed",
        {
            "validated": True,
            "final_trust": {
                "quality_gate": {
                    "status": "pass",
                    "passed": True,
                    "summary": "pass: 0 fail, 0 warn, 4 pass",
                    "checks": [],
                }
            },
        },
    )

    failed = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    failed.write("tool_result", {"name": "run_command", "ok": False, "error": "pytest failed"})
    failed.write("model_error", {"model": "gpt-5.5", "error_type": "ValueError", "error": "bad args"})
    failed.write(
        "tool_result",
        {
            "name": "run_command",
            "args": {"command": 'python -m pytest -q --junitxml="C:/tmp/result.xml"', "cwd": "."},
            "result": {"returncode": 1, "summary": "1 failed"},
            "ok": False,
        },
    )
    failed.write(
        "test_case_result",
        {
            "nodeid": "tests/test_app.py::test_flaky",
            "status": "failed",
            "duration_ms": 120,
            "message": "assert False",
        },
    )
    failed.write(
        "test_case_result",
        {
            "nodeid": "tests/test_app.py::test_slow",
            "status": "passed",
            "duration_ms": 2500,
        },
    )
    failed.finish(
        "completed",
        {
            "validated": False,
            "validation_failed": True,
            "changed_paths": ["kagent/app.py"],
            "last_validation_summary": "1 failed",
            "final_trust": {
                "quality_gate": {
                    "status": "fail",
                    "passed": False,
                    "summary": "fail: 2 fail, 1 warn, 2 pass",
                    "checks": [
                        {"code": "changes_validated", "status": "fail", "message": "not validated"},
                        {"code": "model_errors_absent", "status": "warn", "message": "model error"},
                    ],
                }
            },
        },
    )

    analytics = build_run_analytics(limit=10)
    markdown = format_run_analytics_markdown(analytics)

    assert analytics["run_count"] == 2
    assert analytics["status_counts"]["completed"] == 2
    assert analytics["quality_gate_counts"]["pass"] == 1
    assert analytics["quality_gate_counts"]["fail"] == 1
    assert analytics["validation_failed_count"] == 1
    assert analytics["unverified_count"] == 1
    assert analytics["failed_tool_run_count"] == 1
    assert analytics["model_error_run_count"] == 1
    assert analytics["validation_failed_rate"] == 0.5
    assert analytics["top_quality_gate_checks"][0] == {"name": "fail:changes_validated", "count": 1}
    assert {"name": "run_command", "count": 2} in analytics["top_failed_tools"]
    assert analytics["top_model_errors"] == [{"name": "gpt-5.5:ValueError", "count": 1}]
    assert analytics["top_validation_commands"] == [{"name": "python -m pytest -q", "count": 1}]
    assert analytics["test_case_count"] == 2
    assert analytics["test_status_counts"] == {"failed": 1, "passed": 1}
    assert analytics["top_failed_tests"] == [{"name": "tests/test_app.py::test_flaky", "count": 1}]
    assert analytics["slowest_tests"][0] == {"name": "tests/test_app.py::test_slow", "duration_ms": 2500}
    assert analytics["recent_problem_runs"][0]["quality_gate_status"] == "fail"

    assert "# Run Analytics" in markdown
    assert "validation_failed_rate" in markdown
    assert "`fail:changes_validated`: 1" in markdown
    assert "`gpt-5.5:ValueError`: 1" in markdown
    assert "## Test Cases" in markdown
    assert "`tests/test_app.py::test_flaky`: 1" in markdown
    assert "`tests/test_app.py::test_slow`: 2500ms" in markdown


def test_build_run_analytics_handles_empty_history(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path))

    analytics = build_run_analytics()
    markdown = format_run_analytics_markdown(analytics)

    assert analytics["run_count"] == 0
    assert analytics["validation_failed_rate"] == 0.0
    assert analytics["top_issue_codes"] == []
    assert analytics["test_case_count"] == 0
    assert "- none" in markdown


def test_build_run_analytics_can_filter_by_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path))

    target_workspace = tmp_path / "target"
    other_workspace = tmp_path / "other"
    target = RunLogger(session_id="session-1", workspace_root=str(target_workspace))
    target.finish("completed", {"validated": True})
    other = RunLogger(session_id="session-2", workspace_root=str(other_workspace))
    other.finish("completed", {"validated": False, "validation_failed": True})

    analytics = build_run_analytics(workspace_root=target_workspace)

    assert analytics["run_count"] == 1
    assert analytics["validation_failed_count"] == 0
    assert analytics["status_counts"] == {"completed": 1}


def test_build_run_analytics_detects_timing_regression(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path))

    # A test whose duration jumps from a 100ms baseline to 400ms on the latest run.
    # Created oldest-first so the reversed (newest-first) history ends at 400ms.
    for ms in (100, 100, 100, 100, 200, 400):
        log = RunLogger(session_id="s", workspace_root=str(tmp_path))
        log.write(
            "test_case_result",
            {"nodeid": "tests/test_app.py::test_slow", "status": "passed", "duration_ms": ms},
        )
        log.finish("completed", {"validated": True})

    # A stable test that never regresses (tiny jitter around 100ms).
    for ms in (100, 95, 105, 100, 98, 102):
        log = RunLogger(session_id="s", workspace_root=str(tmp_path))
        log.write(
            "test_case_result",
            {"nodeid": "tests/test_app.py::test_stable", "status": "passed", "duration_ms": ms},
        )
        log.finish("completed", {"validated": True})

    # A validation command with a duration trend across runs.
    for ms in (2000, 2100, 4000):
        log = RunLogger(session_id="s", workspace_root=str(tmp_path))
        log.write(
            "tool_result",
            {
                "name": "run_command",
                "args": {"command": "python -m pytest -q", "cwd": "."},
                "result": {"returncode": 0, "duration_ms": ms},
                "ok": True,
            },
        )
        log.finish("completed", {"validated": True})

    analytics = build_run_analytics(limit=50)

    regressions = {item["nodeid"]: item for item in analytics["timing_regressions"]}
    assert "tests/test_app.py::test_slow" in regressions
    slow = regressions["tests/test_app.py::test_slow"]
    assert slow["current_ms"] == 400
    assert slow["baseline_ms"] == 100
    assert slow["ratio"] == 4.0
    assert slow["delta_ms"] == 300
    assert slow["samples"] == 6
    assert slow["trend"] == "slower"
    assert "tests/test_app.py::test_stable" not in regressions

    command_trends = {item["command"]: item for item in analytics["validation_command_trends"]}
    assert "python -m pytest -q" in command_trends
    assert command_trends["python -m pytest -q"]["samples"] == 3
    assert command_trends["python -m pytest -q"]["avg_ms"] == 2700

    slow_trends = {item["nodeid"]: item for item in analytics["test_duration_trends"]}
    assert slow_trends["tests/test_app.py::test_slow"]["recent_ms"] == 400

    markdown = format_run_analytics_markdown(analytics)
    assert "## Timing Regressions" in markdown
    assert "## Validation Command Trends" in markdown
    assert "tests/test_app.py::test_slow" in markdown
    assert "4.0x" in markdown
    assert "python -m pytest -q" in markdown


def test_build_run_analytics_timing_handles_insufficient_history(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path))

    # A single sample is not enough to establish a baseline -> no regression.
    log = RunLogger(session_id="s", workspace_root=str(tmp_path))
    log.write(
        "test_case_result",
        {"nodeid": "tests/test_app.py::test_once", "status": "passed", "duration_ms": 5000},
    )
    log.finish("completed", {"validated": True})

    analytics = build_run_analytics(limit=50)

    assert analytics["timing_regressions"] == []
    assert analytics["test_duration_trends"] == []
    markdown = format_run_analytics_markdown(analytics)
    assert "## Timing Regressions" in markdown
    assert "- none" in markdown
