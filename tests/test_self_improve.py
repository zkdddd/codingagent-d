from kagent.agent.code_agent import CodeAgent
from kagent.agent.run_log import RunLogger
from kagent.agent.self_improve import suggest_self_improvements
from kagent.agent.tool_schema import tool_schema


def test_suggest_self_improvements_returns_ranked_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr("kagent.agent.run_history.STATE_DIR", str(tmp_path / "runs"))

    package = tmp_path / "kagent" / "agent"
    package.mkdir(parents=True)
    (package / "feature.py").write_text("def run():\n    pass\n", encoding="utf-8")
    (package / "todo.py").write_text("# TODO: improve this\n", encoding="utf-8")
    long_file = package / "large.py"
    long_file.write_text("\n".join("x = 1" for _ in range(520)), encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_existing.py").write_text("def test_existing(): pass\n", encoding="utf-8")

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.finish(
        "completed",
        {
            "validated": True,
            "validation_failed": True,
            "changed_paths": ["kagent/agent/feature.py"],
            "final_trust": {
                "quality_gate": {
                    "status": "fail",
                    "passed": False,
                    "summary": "fail: 2 fail, 1 warn, 2 pass",
                    "checks": [],
                }
            },
        },
    )

    result = suggest_self_improvements(tmp_path, limit=5)

    assert result["ok"] is True
    assert result["suggestions"]
    kinds = [item["kind"] for item in result["suggestions"]]
    assert "failed_runs" in kinds
    assert "missing_tests" in kinds
    assert "long_files" in kinds
    assert any(item["title"] == "Make quality-gate failures easier to recover from" for item in result["suggestions"])
    assert all(item["action"] for item in result["suggestions"])
    assert all(item["validation"] for item in result["suggestions"])


def test_suggest_self_improvements_is_available_as_agent_tool(tmp_path):
    tool_names = {item["function"]["name"] for item in tool_schema()}
    assert "suggest_self_improvements" in tool_names

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    result = agent._dispatch_tool("suggest_self_improvements", {"limit": 2})

    assert result["ok"] is True
    assert len(result["suggestions"]) <= 2


def test_find_symbol_context_is_available_as_agent_tool(tmp_path):
    tool_names = {item["function"]["name"] for item in tool_schema()}
    assert "find_symbol_context" in tool_names

    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text(
        "def build_plan():\n    return 'ok'\n",
        encoding="utf-8",
    )

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    result = agent._dispatch_tool(
        "find_symbol_context",
        {"query": "build_plan", "kind": "function", "context_lines": 0},
    )

    assert result["query"] == "build_plan"
    assert result["contexts"][0]["path"] == "kagent/module.py"
    assert "def build_plan" in result["contexts"][0]["content"]


def test_find_symbol_references_is_available_as_agent_tool(tmp_path):
    tool_names = {item["function"]["name"] for item in tool_schema()}
    assert "find_symbol_references" in tool_names

    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text(
        "def build_plan():\n    return 1\n\ndef run():\n    return build_plan()\n",
        encoding="utf-8",
    )

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    result = agent._dispatch_tool(
        "find_symbol_references",
        {"query": "build_plan", "include_tests": True},
    )

    assert result["query"] == "build_plan"
    assert any(item["reference_type"] == "call" for item in result["references"])


def test_symbol_change_plan_is_available_as_agent_tool(tmp_path):
    tool_names = {item["function"]["name"] for item in tool_schema()}
    assert "symbol_change_plan" in tool_names

    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text(
        "def build_plan():\n    return 1\n\ndef run():\n    return build_plan()\n",
        encoding="utf-8",
    )

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    result = agent._dispatch_tool(
        "symbol_change_plan",
        {"symbol_name": "build_plan", "kind": "function"},
    )

    assert result["ok"] is True
    assert result["symbol"] == "build_plan"
    assert result["primary_definition"]["path"] == "kagent/module.py"
    assert result["references"]
