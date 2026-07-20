import json

import pytest

from kagent.agent.run_log import RunLogger, latest_run_log, read_run_events, summarize_run_log


def test_run_logger_writes_jsonl_events(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("agent_status", {"phase": "planning"})
    logger.finish("completed", {"changed_paths": ["kagent/context.py"]})

    lines = logger.path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]

    assert logger.run_id
    assert logger.path.parent == tmp_path / "runs"
    assert [event["event"] for event in events] == [
        "run_start",
        "agent_status",
        "run_finish",
    ]
    assert events[-1]["data"]["status"] == "completed"


def test_read_and_summarize_run_log(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("agent_status", {"phase": "planning"})
    logger.write("tool_call", {"name": "read_file"})
    logger.write("agent_status", {"phase": "validating"})
    logger.finish(
        "completed",
        {
            "changed_paths": ["kagent/context.py"],
            "symbol_impacts": [
                {
                    "symbol": "manage_context",
                    "definition_path": "kagent/context.py",
                    "reference_count": 4,
                    "related_tests": ["tests/test_context.py"],
                }
            ],
            "validated": True,
            "validation_failed": False,
            "last_validation_summary": "pytest passed",
            "final_trust": {
                "health": "pass",
                "quality_gate": {
                    "status": "pass",
                    "passed": True,
                    "summary": "pass: 0 fail, 0 warn, 4 pass",
                    "checks": [],
                },
            },
        },
    )

    events = read_run_events(logger.path)
    summary = summarize_run_log(logger.path)

    assert len(events) == 5
    assert summary["run_id"] == logger.run_id
    assert summary["session_id"] == "session-1"
    assert summary["workspace_root"] == str(tmp_path)
    assert summary["status"] == "completed"
    assert summary["event_counts"]["agent_status"] == 2
    assert summary["last_phase"] == "validating"
    assert summary["tool_call_count"] == 1
    assert summary["model_request_count"] == 0
    assert summary["changed_paths"] == ["kagent/context.py"]
    assert summary["symbol_impacts"][0]["symbol"] == "manage_context"
    assert summary["symbol_impacts"][0]["related_tests"] == ["tests/test_context.py"]
    assert summary["last_validation_summary"] == "pytest passed"
    assert summary["quality_gate"]["status"] == "pass"


def test_latest_run_log_returns_newest_jsonl(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    older = runs_dir / "2026-01-01-older.jsonl"
    newer = runs_dir / "2026-01-02-newer.jsonl"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")

    assert latest_run_log(runs_dir) == newer


def test_read_run_events_rejects_invalid_json(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_text('{"ok": true}\nnot-json\n', encoding="utf-8")

    with pytest.raises(ValueError, match="line 2"):
        read_run_events(path)
