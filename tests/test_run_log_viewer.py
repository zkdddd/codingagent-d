import json

from kagent.agent.run_log import RunLogger
from kagent.agent.run_log_viewer import (
    find_run_log,
    run_log_timeline,
    summarize_latest_run_for_display,
    summarize_run_for_display,
)


def test_find_run_log_by_run_id(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_log_viewer.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.finish("completed")

    assert find_run_log(logger.run_id) == logger.path
    assert find_run_log("missing-run") is None


def test_run_log_timeline_extracts_readable_events(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("agent_status", {"phase": "planning", "detail": "Inspecting files"})
    logger.write(
        "change_plan",
        {
            "plan": {
                "operation": "patch",
                "target_summary": "kagent/context.py",
                "risk_summary": "risk=low; can change source content",
                "validation_hint": "Run related tests.",
            }
        },
    )
    logger.write(
        "model_request",
        {
            "model": "gpt-5.5",
            "reasoning_effort": "high",
            "stream": True,
            "has_tools": True,
        },
    )
    logger.write(
        "model_response",
        {
            "model": "gpt-5.5",
            "reasoning_effort": "high",
            "stream": True,
            "has_tools": True,
            "duration_ms": 123,
        },
    )
    logger.write("tool_call", {"name": "read_file", "args": {"path": "README.md"}})
    logger.write("tool_result", {"name": "read_file", "ok": True, "summary": "Read README"})
    logger.write(
        "tool_result",
        {
            "name": "validation_plan",
            "result": {
                "summary": "Detected a Python project.",
                "selection": {
                    "strategy": "Run fast syntax checks first, then related tests, then full project validation when available."
                },
            },
        },
    )
    logger.finish("completed")

    timeline = run_log_timeline(logger.path)

    assert [item["title"] for item in timeline] == [
        "Run started",
        "Phase: planning",
        "Change plan: patch -> kagent/context.py",
        "Model request: gpt-5.5/high",
        "Model response: gpt-5.5/high",
        "Tool call: read_file",
        "Tool result: read_file (ok)",
        "Tool result: validation_plan (ok)",
        "Run finished: completed",
    ]
    assert timeline[1]["detail"] == "Inspecting files"
    assert timeline[2]["detail"] == "risk=low; can change source content"
    assert timeline[4]["detail"] == "123ms, tools, stream"
    assert timeline[6]["detail"] == "Read README"
    assert timeline[7]["detail"].startswith("Run fast syntax checks first")


def test_summarize_run_for_display_includes_debugging_signals(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("agent_status", {"phase": "validating"})
    logger.write("model_request", {"model": "gpt-5.5", "reasoning_effort": "high"})
    logger.write(
        "model_error",
        {
            "model": "gpt-5.5",
            "reasoning_effort": "high",
            "error_type": "ValueError",
            "error": "unsupported parameter: reasoning_effort",
            "will_retry_without_reasoning": True,
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
    logger.write(
        "model_response",
        {
            "model": "gpt-5.5",
            "reasoning_effort": None,
            "fallback_without_reasoning": True,
            "duration_ms": 55,
        },
    )
    logger.write("tool_call", {"name": "run_command"})
    logger.write(
        "tool_result",
        {
            "name": "run_command",
            "result": {"ok": False, "summary": "pytest failed"},
        },
    )
    logger.write("tool_loop_warning", {"message": "Repeated failed command"})
    logger.write("patch_recovery", {"summary": "Read current file context"})
    logger.write("failure_focus", {"targets": [{"path": "tests/test_app.py", "line": 12}]})
    logger.finish(
        "failed",
        {
            "changed_paths": ["kagent/agent/run_log_viewer.py"],
            "validation_failed": True,
            "last_validation_summary": "1 failed",
        },
    )

    display = summarize_run_for_display(logger.path)

    assert "status: failed" in display
    assert "last_phase: validating" in display
    assert "tools: run_command x1" in display
    assert "model_requests: gpt-5.5/high x1, gpt-5.5/no-reasoning fallback x1" in display
    assert "model_fallbacks: 1" in display
    assert "model_errors: gpt-5.5 ValueError: unsupported parameter: reasoning_effort" in display
    assert "failed_tools: run_command (pytest failed)" in display
    assert "validation: failed: 1 failed" in display
    assert "changed_paths: kagent/agent/run_log_viewer.py" in display
    assert "loop_warnings: Repeated failed command" in display
    assert "patch_recovery: Read current file context" in display
    assert "failure_focus: 1 target(s)" in display


def test_summarize_latest_run_for_display_returns_none_without_logs(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log_viewer.STATE_DIR", str(tmp_path))

    assert summarize_latest_run_for_display() is None


def test_find_run_log_ignores_broken_jsonl(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    broken = runs_dir / "2026-01-01-run-1.jsonl"
    valid = runs_dir / "2026-01-01-run-2.jsonl"
    broken.write_text("not-json", encoding="utf-8")
    valid.write_text(
        json.dumps({"run_id": "run-2", "event": "run_start", "data": {}}),
        encoding="utf-8",
    )

    assert find_run_log("run-2", runs_dir) == valid
