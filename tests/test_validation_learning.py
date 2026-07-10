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
            "result": {"returncode": 0},
            "ok": True,
        },
    )
    logger.finish("completed", {"validated": True})

    learned = learned_validation_commands_from_runs()

    assert learned[0]["command"] == "run-tests.bat"
    assert learned[0]["learned"] is True
    assert learned[0]["success_count"] == 1
    assert learned[0]["failure_count"] == 0
    assert learned[0]["confidence"] == 1.0


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


def test_validation_plan_prioritizes_learned_commands(tmp_path, monkeypatch):
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

    assert plan["commands"][0]["command"] == "run-tests.bat"
    assert plan["commands"][0]["learned"] is True
