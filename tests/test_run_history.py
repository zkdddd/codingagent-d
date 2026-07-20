import json
import os

from kagent.agent.run_history import (
    export_latest_run_markdown,
    export_run_markdown,
    list_run_history,
)
from kagent.agent.run_log import RunLogger


def test_list_run_history_returns_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path))

    older = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    older.finish("completed", {"validated": True})
    newer = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    newer.finish("completed", {"validated": True})
    os.utime(older.path, (100, 100))
    os.utime(newer.path, (200, 200))

    rows = list_run_history()

    assert [row["run_id"] for row in rows] == [newer.run_id, older.run_id]
    assert rows[0]["status"] == "completed"
    assert rows[0]["health"] == "pass"
    assert rows[0]["validated"] is True


def test_list_run_history_filters_failed_unverified_and_failed_tools(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path))

    clean = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    clean.finish("completed", {"validated": True})
    unverified = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    unverified.finish("completed", {"validated": False, "changed_paths": ["kagent/app.py"]})
    failed_tool = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    failed_tool.write("tool_result", {"name": "run_command", "ok": False, "error": "boom"})
    failed_tool.finish("completed", {"validated": True})
    validation_failed = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    validation_failed.finish(
        "completed",
        {"validated": True, "validation_failed": True, "last_validation_summary": "1 failed"},
    )
    gate_failed = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    gate_failed.finish(
        "completed",
        {
            "validated": True,
            "final_trust": {
                "quality_gate": {
                    "status": "fail",
                    "passed": False,
                    "summary": "fail: 1 fail, 0 warn, 4 pass",
                    "checks": [],
                }
            },
        },
    )

    assert [row["run_id"] for row in list_run_history(health="pass")] == [
        gate_failed.run_id,
        clean.run_id,
    ]
    assert [row["run_id"] for row in list_run_history(unverified=True)] == [unverified.run_id]
    assert [row["run_id"] for row in list_run_history(failed_tools=True)] == [failed_tool.run_id]
    assert [row["run_id"] for row in list_run_history(validation_failed=True)] == [
        validation_failed.run_id
    ]
    assert [row["run_id"] for row in list_run_history(quality_gate_status="fail")] == [
        gate_failed.run_id
    ]


def test_export_run_markdown_contains_summary_self_check_and_timeline(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_log_viewer.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("agent_status", {"phase": "planning", "detail": "Inspecting files"})
    logger.write("tool_call", {"name": "read_file", "summary": "Read README"})
    logger.finish("completed", {"validated": True, "changed_paths": ["README.md"]})

    markdown = export_run_markdown(logger.run_id)

    assert markdown is not None
    assert "# Agent Run Export" in markdown
    assert "## Summary" in markdown
    assert "Run Log Summary" in markdown
    assert "## Self Check" in markdown
    assert "Agent Self Check" in markdown
    assert "## Timeline" in markdown
    assert "Phase: planning - Inspecting files" in markdown
    assert export_latest_run_markdown() == markdown
    assert export_run_markdown("missing-run") is None


def test_list_run_history_ignores_broken_logs(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    broken = runs_dir / "2026-01-01-broken.jsonl"
    valid = runs_dir / "2026-01-01-valid.jsonl"
    broken.write_text("not-json", encoding="utf-8")
    valid.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:00Z",
                        "run_id": "run-1",
                        "event": "run_start",
                        "data": {"session_id": "session-1", "workspace_root": str(tmp_path)},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:01Z",
                        "run_id": "run-1",
                        "event": "run_finish",
                        "data": {"status": "completed", "validated": True},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    rows = list_run_history(runs_dir)

    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-1"
