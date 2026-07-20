from pathlib import Path

from kagent.agent.validation import build_validation_plan
from kagent.agent.validation_learning import learned_validation_commands_from_runs
from kagent.agent.run_log import RunLogger


class StubWorkspace:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _rel(self, path: Path | None) -> str:
        if path is None:
            return "."
        try:
            return str(path.resolve().relative_to(self.root)) or "."
        except ValueError:
            return str(path)


def test_learned_validation_commands_use_successful_planned_commands(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.validation_learning.STATE_DIR", str(tmp_path))
    command = {
        "label": "Project verification",
        "command": "run-tests.bat",
        "cwd": ".",
        "timeout_ms": 240000,
    }
    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("tool_result", {"name": "validation_plan", "result": {"commands": [command]}, "ok": True})
    logger.write(
        "tool_result",
        {
            "name": "run_command",
            "args": {"command": "run-tests.bat", "cwd": "."},
            "result": {"returncode": 0, "duration_ms": 1200},
            "ok": True,
        },
    )
    logger.finish("completed", {"validated": True})

    learned = learned_validation_commands_from_runs()

    assert learned[0]["command"] == "run-tests.bat"
    assert learned[0]["learned"] is True
    assert learned[0]["success_count"] == 1
    assert learned[0]["failure_count"] == 0
    assert learned[0]["attempt_count"] == 1
    assert learned[0]["success_rate"] == 1.0
    assert learned[0]["failure_rate"] == 0.0
    assert learned[0]["avg_duration_ms"] == 1200
    assert learned[0]["last_failure_summary"] == ""
    assert learned[0]["confidence"] == 1.0


def test_learned_validation_commands_track_failures_and_duration(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.validation_learning.STATE_DIR", str(tmp_path))
    command = {
        "label": "Pytest suite",
        "command": "python -m pytest -q",
        "cwd": ".",
        "timeout_ms": 240000,
    }
    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("tool_result", {"name": "validation_plan", "result": {"commands": [command]}, "ok": True})
    logger.write(
        "tool_result",
        {
            "name": "run_command",
            "args": {"command": "python -m pytest -q", "cwd": "."},
            "result": {"returncode": 1, "summary": "1 failed", "duration_ms": 3000},
            "ok": False,
        },
    )
    logger.write(
        "tool_result",
        {
            "name": "run_command",
            "args": {"command": "python -m pytest -q", "cwd": "."},
            "result": {"returncode": 0, "summary": "12 passed", "duration_ms": 1000},
            "ok": True,
        },
    )
    logger.finish("completed", {"validated": True})

    learned = learned_validation_commands_from_runs(max_failure_rate=0.5)

    assert learned[0]["command"] == "python -m pytest -q"
    assert learned[0]["success_count"] == 1
    assert learned[0]["failure_count"] == 1
    assert learned[0]["attempt_count"] == 2
    assert learned[0]["success_rate"] == 0.5
    assert learned[0]["failure_rate"] == 0.5
    assert learned[0]["avg_duration_ms"] == 2000
    assert learned[0]["last_failure_summary"] == "1 failed"
    assert "50.0% success" in learned[0]["reason"]
    assert "last failure: 1 failed" in learned[0]["reason"]


def test_learned_validation_commands_ignore_unplanned_shell_commands(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.validation_learning.STATE_DIR", str(tmp_path))
    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write(
        "tool_result",
        {
            "name": "run_command",
            "args": {"command": "echo ok", "cwd": "."},
            "result": {"returncode": 0},
            "ok": True,
        },
    )
    logger.finish("completed", {"validated": True})

    assert learned_validation_commands_from_runs() == []


def test_validation_plan_keeps_learned_commands_after_fast_checks(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.agent.validation_learning.STATE_DIR", str(tmp_path))
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text("print('ok')\n", encoding="utf-8")
    learned_command = {
        "label": "Project verification",
        "command": "run-tests.bat",
        "cwd": ".",
        "timeout_ms": 240000,
    }
    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write(
        "tool_result",
        {"name": "validation_plan", "result": {"commands": [learned_command]}, "ok": True},
    )
    logger.write(
        "tool_result",
        {
            "name": "run_command",
            "args": {"command": "run-tests.bat", "cwd": "."},
            "result": {"returncode": 0},
            "ok": True,
        },
    )
    logger.finish("completed", {"validated": True})

    plan = build_validation_plan(
        changed_paths={"kagent/module.py"},
        workspace=StubWorkspace(tmp_path),
    )

    assert plan["commands"][0]["label"] == "Python syntax check"
    assert plan["commands"][1]["command"] == "run-tests.bat"
    assert plan["commands"][1]["learned"] is True
