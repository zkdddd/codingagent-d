from kagent.agent.run_log import RunLogger
from kagent.agent.task_resume import (
    build_latest_resume_context,
    build_resume_context,
    build_resume_context_by_id,
    format_resume_context,
)


def test_resume_context_prioritizes_validation_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_log_viewer.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.task_resume.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write(
        "tool_result",
        {
            "name": "run_command",
            "args": {"command": "python -m pytest -q", "cwd": "."},
            "result": {"ok": False, "summary": "1 failed"},
            "ok": False,
        },
    )
    logger.finish(
        "completed",
        {
            "validated": True,
            "validation_failed": True,
            "changed_paths": ["kagent/agent/task_plan.py"],
            "last_validation_summary": "1 failed",
            "plan_snapshot": {
                "total": 5,
                "counts": {"done": 3, "active": 1, "pending": 1},
                "next_action": {
                    "id": "validate_changes",
                    "title": "Validate changed code",
                    "status": "active",
                    "objective": "Run validation.",
                },
                "steps": [],
            },
        },
    )

    context = build_resume_context(logger.path)
    display = format_resume_context(context)

    assert context["priority"] == "fix_validation_failure"
    assert context["next_action"]["id"] == "validate_changes"
    assert context["issue_codes"] == ["validation_failed", "failed_tools"]
    assert "Start by inspecting the validation failure" in context["resume_prompt"]
    assert "priority: fix_validation_failure" in display


def test_resume_context_prioritizes_unverified_changes_from_plan_payload(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.task_resume.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.finish(
        "completed",
        {
            "validated": False,
            "changed_paths": ["kagent/agent/task_resume.py"],
            "plan": [
                {"id": "understand_task", "title": "Understand", "status": "done"},
                {"id": "inspect_context", "title": "Inspect", "status": "done"},
                {
                    "id": "validate_changes",
                    "title": "Validate changed code",
                    "status": "pending",
                    "objective": "Run checks.",
                },
            ],
        },
    )

    context = build_resume_context(logger.path)

    assert context["priority"] == "run_validation"
    assert context["next_action"]["id"] == "validate_changes"
    assert context["plan_snapshot"]["counts"]["done"] == 2
    assert "Start by validating the changed files" in context["resume_prompt"]


def test_resume_context_latest_and_by_id(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_log_viewer.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.task_resume.STATE_DIR", str(tmp_path))

    older = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    older.finish("completed", {"validated": True})
    newer = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    newer.finish(
        "stopped",
        {
            "validated": False,
            "plan_snapshot": {
                "total": 2,
                "counts": {"done": 1, "active": 1},
                "next_action": {"id": "make_changes", "title": "Make changes", "status": "active"},
                "steps": [],
            },
        },
    )

    latest = build_latest_resume_context()
    by_id = build_resume_context_by_id(newer.run_id)

    assert latest["run_id"] == newer.run_id
    assert latest["priority"] == "continue_incomplete_plan"
    assert by_id["run_id"] == newer.run_id
    assert build_resume_context_by_id("missing-run") is None
