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
            "final_trust": {
                "quality_gate": {
                    "status": "fail",
                    "passed": False,
                    "summary": "fail: 1 fail, 1 warn, 3 pass",
                    "checks": [
                        {
                            "code": "validation_failed",
                            "status": "fail",
                            "message": "Validation failure remains recorded.",
                        }
                    ],
                }
            },
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
    assert context["quality_gate"]["status"] == "fail"
    assert "quality_gate" in display
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
            "final_trust": {
                "quality_gate": {
                    "status": "warn",
                    "passed": False,
                    "summary": "warn: 0 fail, 1 warn, 3 pass",
                    "checks": [
                        {
                            "code": "project_rules_checked",
                            "status": "warn",
                            "message": "`KAGENT.md` project rules were not checked.",
                        }
                    ],
                }
            },
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


def test_resume_context_uses_quality_gate_when_no_older_priority_applies(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.task_resume.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.finish(
        "completed",
        {
            "validated": True,
            "changed_paths": [],
            "final_trust": {
                "quality_gate": {
                    "status": "fail",
                    "passed": False,
                    "summary": "fail: 1 fail, 0 warn, 4 pass",
                    "checks": [
                        {
                            "code": "model_errors_absent",
                            "status": "fail",
                            "message": "Model errors were recorded.",
                        }
                    ],
                }
            },
        },
    )

    context = build_resume_context(logger.path)

    assert context["priority"] == "resolve_quality_gate_failure"
    assert context["quality_gate_checks"][0]["code"] == "model_errors_absent"
    assert "Quality gate checks to address" in context["resume_prompt"]
    assert "Start by resolving the failing quality gate check" in context["resume_prompt"]


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
