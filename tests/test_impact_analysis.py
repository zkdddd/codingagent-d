from kagent.agent.impact_analysis import (
    analyze_reference_impact,
    related_test_commands_for_changes,
    related_tests_for_changes,
)


def test_related_tests_for_top_level_module(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_context.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    related = related_tests_for_changes({"kagent/context.py"}, workspace_root=tmp_path)

    assert related == ["tests/test_context.py"]


def test_related_tests_for_nested_module(tmp_path):
    target = tmp_path / "tests" / "agent"
    target.mkdir(parents=True)
    (target / "test_validation.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    related = related_tests_for_changes({"kagent/agent/validation.py"}, workspace_root=tmp_path)

    assert related == ["tests/agent/test_validation.py"]


def test_related_tests_keeps_changed_test_file(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_validation.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    related = related_tests_for_changes({"tests/test_validation.py"}, workspace_root=tmp_path)

    assert related == ["tests/test_validation.py"]


def test_related_test_commands_use_pytest(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_context.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    commands = related_test_commands_for_changes(
        {"kagent/context.py"},
        workspace_root=tmp_path,
        cwd=".",
    )

    assert len(commands) == 1
    assert commands[0]["label"] == "Related tests"
    assert "pytest" in commands[0]["command"]
    assert "tests/test_context.py" in commands[0]["command"]


def test_reference_impact_finds_tests_importing_changed_module(tmp_path):
    package = tmp_path / "kagent" / "agent"
    package.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir()
    (package / "validation.py").write_text(
        "class ValidationPlan: pass\n\ndef build_validation_plan(): pass\n",
        encoding="utf-8",
    )
    (tests / "test_agent_flow.py").write_text(
        "from kagent.agent.validation import ValidationPlan\n"
        "def test_flow():\n"
        "    assert ValidationPlan\n",
        encoding="utf-8",
    )

    impact = analyze_reference_impact("kagent/agent/validation.py", workspace_root=tmp_path)
    related = related_tests_for_changes({"kagent/agent/validation.py"}, workspace_root=tmp_path)

    assert impact["module"] == "kagent.agent.validation"
    assert impact["symbols"] == ["ValidationPlan", "build_validation_plan"]
    assert impact["references"][0]["path"] == "tests/test_agent_flow.py"
    assert impact["related_tests"] == [
        {"path": "tests/test_agent_flow.py", "reason": "references changed module or symbol"}
    ]
    assert related == ["tests/test_agent_flow.py"]


def test_reference_impact_maps_referencing_source_to_its_tests(tmp_path):
    agent_dir = tmp_path / "kagent" / "agent"
    agent_dir.mkdir(parents=True)
    tests_dir = tmp_path / "tests" / "agent"
    tests_dir.mkdir(parents=True)
    (agent_dir / "validation.py").write_text(
        "def build_validation_plan(): pass\n",
        encoding="utf-8",
    )
    (agent_dir / "code_agent.py").write_text(
        "from kagent.agent.validation import build_validation_plan\n"
        "def run():\n"
        "    return build_validation_plan()\n",
        encoding="utf-8",
    )
    (tests_dir / "test_code_agent.py").write_text("def test_run(): pass\n", encoding="utf-8")

    impact = analyze_reference_impact("kagent/agent/validation.py", workspace_root=tmp_path)
    related = related_tests_for_changes({"kagent/agent/validation.py"}, workspace_root=tmp_path)

    assert impact["references"][0]["path"] == "kagent/agent/code_agent.py"
    assert impact["related_tests"] == [
        {
            "path": "tests/agent/test_code_agent.py",
            "reason": "covers referencing source kagent/agent/code_agent.py",
        }
    ]
    assert related == ["tests/agent/test_code_agent.py"]
