import json
from pathlib import Path

from kagent.agent.validation import (
    build_focused_validation_commands,
    build_validation_plan,
    validation_result_summary,
    validation_failure_prompt,
    validation_prompt,
)


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


def test_python_changed_file_gets_py_compile_plan(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    package = tmp_path / "kagent"
    package.mkdir()
    changed_file = package / "module.py"
    changed_file.write_text("print('ok')\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_module.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    plan = build_validation_plan(
        changed_paths={"kagent/module.py"},
        workspace=StubWorkspace(tmp_path),
    )

    assert plan["project_type"] == "python"
    assert plan["command_count"] >= 1
    assert plan["commands"][0]["label"] == "Python syntax check"
    assert "py_compile" in plan["commands"][0]["command"]
    assert plan["commands"][1]["label"] == "Related tests"
    assert "tests/test_module.py" in plan["commands"][1]["command"]
    assert plan["commands"][1]["related_reason"] == "matches changed source kagent/module.py"
    assert plan["commands"][2]["label"] == "Pytest suite"
    assert "pytest -q" in plan["commands"][2]["command"]
    assert plan["selection"]["strategy"].startswith("Run fast syntax checks first")
    assert [item["tier"] for item in plan["selection"]["tiers"]] == [
        "syntax",
        "related_tests",
        "full_validation",
    ]


def test_validation_plan_keeps_related_tests_before_learned_commands(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text("print('ok')\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_module.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    monkeypatch.setattr(
        "kagent.agent.validation.learned_validation_commands_from_runs",
        lambda limit=5: [
            {
                "label": "Learned validation",
                "reason": "Learned from history.",
                "command": "python -m pytest tests/test_other.py",
                "cwd": ".",
                "timeout_ms": 120000,
                "learned": True,
                "success_rate": 1.0,
                "failure_rate": 0.0,
                "avg_duration_ms": 900,
            }
        ],
    )

    plan = build_validation_plan(
        changed_paths={"kagent/module.py"},
        workspace=StubWorkspace(tmp_path),
    )

    labels = [command["label"] for command in plan["commands"]]

    assert labels[:2] == ["Python syntax check", "Related tests"]
    assert labels[2] == "Learned validation"
    assert labels[3] == "Pytest suite"
    assert [item["tier"] for item in plan["selection"]["tiers"]] == [
        "syntax",
        "related_tests",
        "learned",
        "full_validation",
    ]
    assert plan["selection"]["tiers"][2]["success_rate"] == 1.0
    assert plan["selection"]["tiers"][2]["selection_score"] > plan["selection"]["tiers"][3]["selection_score"]


def test_validation_plan_demotes_unreliable_learned_commands(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(
        "kagent.agent.validation.learned_validation_commands_from_runs",
        lambda limit=5: [
            {
                "label": "Learned validation",
                "reason": "Learned but unreliable.",
                "command": "python -m pytest tests/flaky.py",
                "cwd": ".",
                "timeout_ms": 120000,
                "learned": True,
                "success_rate": 0.25,
                "failure_rate": 0.75,
                "avg_duration_ms": 80000,
            }
        ],
    )

    plan = build_validation_plan(
        changed_paths={"kagent/module.py"},
        workspace=StubWorkspace(tmp_path),
    )

    labels = [command["label"] for command in plan["commands"]]

    assert labels[:2] == ["Python syntax check", "Pytest suite"]
    assert labels[2] == "Learned validation"
    assert plan["selection"]["tiers"][1]["tier"] == "full_validation"
    assert plan["selection"]["tiers"][2]["tier"] == "learned"


def test_validation_plan_uses_symbol_impacts_before_full_validation(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    package = tmp_path / "kagent" / "agent"
    package.mkdir(parents=True)
    (package / "validation.py").write_text("def build_validation_plan(): pass\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_symbol_validation.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    plan = build_validation_plan(
        changed_paths={"kagent/agent/validation.py"},
        workspace=StubWorkspace(tmp_path),
        symbol_impacts=[
            {
                "symbol": "build_validation_plan",
                "definition_path": "kagent/agent/validation.py",
                "related_tests": ["tests/test_symbol_validation.py"],
                "validation_commands": [
                    "python -m pytest -q tests/test_symbol_validation.py"
                ],
            }
        ],
    )

    labels = [command["label"] for command in plan["commands"]]

    assert labels[:3] == ["Python syntax check", "Related symbol test", "Pytest suite"]
    assert plan["commands"][1]["symbol"] == "build_validation_plan"
    assert plan["commands"][1]["related_reason"] == "symbol impact: build_validation_plan"
    assert "tests/test_symbol_validation.py" in plan["commands"][1]["command"]
    assert [item["tier"] for item in plan["selection"]["tiers"]] == [
        "syntax",
        "symbol_related_tests",
        "full_validation",
    ]
    assert plan["selection"]["tiers"][1]["symbol"] == "build_validation_plan"


def test_python_project_prefers_verify_script_when_available(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "verify.ps1").write_text("python -m pytest -q\n", encoding="utf-8")
    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text("print('ok')\n", encoding="utf-8")

    plan = build_validation_plan(
        changed_paths={"kagent/module.py"},
        workspace=StubWorkspace(tmp_path),
    )

    assert plan["commands"][1]["label"] == "Project verification"
    assert "scripts/verify.ps1" in plan["commands"][1]["command"]


def test_node_project_uses_declared_script_priority(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest", "lint": "eslint ."}}),
        encoding="utf-8",
    )
    changed_file = tmp_path / "src" / "app.ts"
    changed_file.parent.mkdir()
    changed_file.write_text("export const ok = true;\n", encoding="utf-8")

    plan = build_validation_plan(
        changed_paths={"src/app.ts"},
        workspace=StubWorkspace(tmp_path),
    )

    assert plan["project_type"] == "node"
    assert plan["commands"][0]["label"] == "Lint"
    assert plan["commands"][0]["command"] == "npm run lint"


def test_docs_only_changes_get_no_command_but_clear_prompt(tmp_path):
    (tmp_path / "README.md").write_text("# Docs\n", encoding="utf-8")

    plan = build_validation_plan(
        changed_paths={"README.md"},
        workspace=StubWorkspace(tmp_path),
    )

    assert plan["project_type"] == "docs"
    assert plan["commands"] == []
    assert "documentation or config-only" in plan["summary"]
    assert "No safe automatic validation command" in validation_prompt({"README.md"}, plan)


def test_validation_failure_prompt_includes_attempt_and_summary():
    prompt = validation_failure_prompt(
        changed_paths={"kagent/agent/code_agent.py"},
        summary="py_compile failed",
        plan={
            "commands": [
                {"label": "Python syntax check", "command": "python -m py_compile file.py"}
            ]
        },
        attempt=2,
        max_attempts=3,
    )

    assert "py_compile failed" in prompt
    assert "repair attempt 2 of 3" in prompt
    assert "Failure category:" in prompt
    assert "Repair strategy:" in prompt
    assert "Python syntax check" in prompt


def test_validation_failure_prompt_includes_symbol_impacts():
    prompt = validation_failure_prompt(
        changed_paths={"kagent/agent/validation.py"},
        summary="FAILED tests/test_validation.py::test_plan",
        symbol_impacts=[
            {
                "symbol": "build_validation_plan",
                "definition_path": "kagent/agent/validation.py",
                "reference_count": 12,
                "related_tests": ["tests/test_validation.py"],
            }
        ],
    )

    assert "Symbol impact to consider while repairing" in prompt
    assert "`build_validation_plan` at `kagent/agent/validation.py`" in prompt
    assert "related tests: tests/test_validation.py" in prompt


def test_validation_result_summary_explains_missing_pytest():
    summary = validation_result_summary(
        {
            "summary": "Exit 1",
            "stderr": "D:\\python\\python.exe: No module named pytest",
        },
        {"label": "Pytest suite", "command": "python -m pytest -q"},
    )

    assert summary is not None
    assert "Pytest is not installed" in summary
    assert "python -m pip install -r requirements.txt" in summary


def test_validation_result_summary_includes_failure_locations():
    summary = validation_result_summary(
        {
            "summary": "Exit 1",
            "stdout": "FAILED tests/test_context.py::test_context_failure\n",
        },
        {"label": "Pytest suite", "command": "python -m pytest -q"},
    )

    assert summary is not None
    assert "Failure locations" in summary
    assert "tests/test_context.py::test_context_failure" in summary


def test_focused_validation_command_for_pytest_nodeid():
    commands = build_focused_validation_commands(
        [
            {
                "kind": "pytest_failed_node",
                "nodeid": "tests/test_context.py::test_context_failure",
            }
        ],
        base_command={"cwd": "."},
    )

    assert len(commands) == 1
    assert "pytest" in commands[0]["command"]
    assert "tests/test_context.py::test_context_failure" in commands[0]["command"]
    assert commands[0]["cwd"] == "."


def test_focused_validation_command_for_source_file_uses_py_compile():
    commands = build_focused_validation_commands(
        [
            {
                "kind": "python_traceback",
                "path": "kagent/context.py",
                "line": 12,
            }
        ],
        base_command={"cwd": "."},
    )

    assert len(commands) == 1
    assert "py_compile" in commands[0]["command"]
    assert "kagent/context.py" in commands[0]["command"]


def test_focused_validation_command_for_test_file_uses_pytest_file():
    commands = build_focused_validation_commands(
        [
            {
                "kind": "file_line",
                "path": "tests/test_context.py",
                "line": 12,
            }
        ],
        base_command={"cwd": "."},
    )

    assert len(commands) == 1
    assert "pytest" in commands[0]["command"]
    assert "tests/test_context.py" in commands[0]["command"]
