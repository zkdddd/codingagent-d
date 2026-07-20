from types import SimpleNamespace

from kagent import db
from kagent.agent.code_agent import AgentRunState, CodeAgent
from kagent.agent.run_log import read_run_events


def test_code_agent_injects_project_memory_into_model_messages(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.db.DB_PATH", str(tmp_path / "kagent.db"))
    monkeypatch.setattr("kagent.agent.workspace.ROLLBACK_ROOT", str(tmp_path / "rollback"))
    db.init_db()

    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "run-tests.bat").write_text("python -m pytest -q\n", encoding="utf-8")

    captured = {}

    def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return [_chunk(content="完成")]

    monkeypatch.setattr("kagent.agent.code_agent.create_chat_completion_with_reasoning", fake_create)

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    report = agent.run([{"role": "user", "content": "说明项目"}], max_rounds=1)

    system_messages = [
        message["content"]
        for message in captured["messages"]
        if message.get("role") == "system"
    ]
    assert "完成" in report
    assert any("Long-term project memory." in content for content in system_messages)
    assert any("run-tests.bat" in content for content in system_messages)


def test_code_agent_injects_project_rules_into_model_messages(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.db.DB_PATH", str(tmp_path / "kagent.db"))
    monkeypatch.setattr("kagent.agent.workspace.ROLLBACK_ROOT", str(tmp_path / "rollback"))
    db.init_db()

    (tmp_path / "KAGENT.md").write_text(
        "# KAGENT.md\n\n- Always run the targeted pytest file first.\n",
        encoding="utf-8",
    )

    captured = {}

    def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return [_chunk(content="done")]

    monkeypatch.setattr("kagent.agent.code_agent.create_chat_completion_with_reasoning", fake_create)

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    agent.run([{"role": "user", "content": "update code"}], max_rounds=1)

    system_text = "\n\n".join(
        message["content"]
        for message in captured["messages"]
        if message.get("role") == "system"
    )
    assert "Project rules from KAGENT.md." in system_text
    assert "Always run the targeted pytest file first." in system_text


def test_code_agent_injects_project_rules_health_warning(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.db.DB_PATH", str(tmp_path / "kagent.db"))
    monkeypatch.setattr("kagent.agent.workspace.ROLLBACK_ROOT", str(tmp_path / "rollback"))
    db.init_db()

    (tmp_path / "KAGENT.md").write_text(
        "# KAGENT.md\n\n## Project Overview\n\n- Project.\n",
        encoding="utf-8",
    )

    captured = {}
    events = []

    def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return [_chunk(content="done")]

    monkeypatch.setattr("kagent.agent.code_agent.create_chat_completion_with_reasoning", fake_create)

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    agent.run(
        [{"role": "user", "content": "update code"}],
        max_rounds=1,
        on_event=events.append,
    )

    system_text = "\n\n".join(
        message["content"]
        for message in captured["messages"]
        if message.get("role") == "system"
    )
    project_rule_events = [
        event for event in events if event.get("type") == "project_rules_check"
    ]

    assert "Project rules health check for KAGENT.md." in system_text
    assert "missing_validation_command" in system_text
    assert project_rule_events
    assert project_rule_events[0]["health"] in {"needs_attention", "weak"}


def test_code_agent_final_prompt_includes_trust_check(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.db.DB_PATH", str(tmp_path / "kagent.db"))
    monkeypatch.setattr("kagent.agent.workspace.ROLLBACK_ROOT", str(tmp_path / "rollback"))
    db.init_db()

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    state = AgentRunState(
        content_changed=True,
        changed_paths={"a.py"},
        validated=False,
        validation_failed=False,
    )

    prompt = agent._final_response_prompt(state)

    assert "Final response trust check." in prompt
    assert "unverified_changes" in prompt
    assert "quality_gate" in prompt


def test_code_agent_final_prompt_includes_symbol_impacts(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.db.DB_PATH", str(tmp_path / "kagent.db"))
    monkeypatch.setattr("kagent.agent.workspace.ROLLBACK_ROOT", str(tmp_path / "rollback"))
    db.init_db()

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    state = AgentRunState(
        content_changed=True,
        changed_paths={"kagent/agent/validation.py"},
        validated=True,
        validation_failed=False,
        symbol_change_plans=[
            {
                "ok": True,
                "symbol": "build_validation_plan",
                "primary_definition": {"path": "kagent/agent/validation.py"},
                "definitions": [{"path": "kagent/agent/validation.py"}],
                "reference_count": 12,
                "related_tests": [{"path": "tests/test_validation.py"}],
                "validation_commands": [
                    {"command": "python -m pytest -q tests/test_validation.py"}
                ],
            }
        ],
    )

    prompt = agent._final_response_prompt(state)

    assert "symbol_impacts" in prompt
    assert "build_validation_plan at kagent/agent/validation.py" in prompt
    assert "related_tests: tests/test_validation.py" in prompt


def test_code_agent_annotates_rollback_with_symbol_impacts(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.db.DB_PATH", str(tmp_path / "kagent.db"))
    monkeypatch.setattr("kagent.agent.workspace.ROLLBACK_ROOT", str(tmp_path / "rollback"))
    db.init_db()
    db.create_session("session-1", "Session 1")

    package = tmp_path / "kagent" / "agent"
    package.mkdir(parents=True)
    (package / "validation.py").write_text("def build_validation_plan():\n    return []\n", encoding="utf-8")

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    messages = []
    result, ok, _, _ = agent._execute_tool_action(
        call_id="call-1",
        name="write_file",
        args={
            "path": "kagent/agent/validation.py",
            "content": "def build_validation_plan():\n    return ['ok']\n",
        },
        round_idx=1,
        messages=messages,
        report_parts=[],
        emit=None,
        on_event=None,
        symbol_plans=[
            {
                "ok": True,
                "symbol": "build_validation_plan",
                "primary_definition": {"path": "kagent/agent/validation.py"},
                "definitions": [{"path": "kagent/agent/validation.py"}],
                "reference_count": 12,
                "related_tests": [{"path": "tests/test_validation.py"}],
                "validation_commands": [
                    {"command": "python -m pytest -q tests/test_validation.py"}
                ],
            }
        ],
    )

    preview = agent.workspace.preview_rollback_change(result["rollback_id"])

    assert ok is True
    assert preview["symbol_impacts"][0]["symbol"] == "build_validation_plan"
    assert preview["diff_entries"][0]["symbol_impacts"][0]["symbol"] == "build_validation_plan"


def test_code_agent_injects_runtime_metadata_into_model_messages(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.db.DB_PATH", str(tmp_path / "kagent.db"))
    monkeypatch.setattr("kagent.agent.workspace.ROLLBACK_ROOT", str(tmp_path / "rollback"))
    db.init_db()

    captured = {}

    def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return [_chunk(content="done")]

    monkeypatch.setattr("kagent.agent.code_agent.create_chat_completion_with_reasoning", fake_create)

    agent = CodeAgent(
        workspace_root=str(tmp_path),
        session_id="session-1",
        model="gpt-5.5",
        reasoning_effort="high",
    )
    agent.run([{"role": "user", "content": "what model are you using?"}], max_rounds=1)

    system_text = "\n\n".join(
        message["content"]
        for message in captured["messages"]
        if message.get("role") == "system"
    )
    assert "Current runtime model: gpt-5.5" in system_text
    assert "Current reasoning effort: high" in system_text


def test_code_agent_writes_model_request_events_to_run_log(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.db.DB_PATH", str(tmp_path / "kagent.db"))
    monkeypatch.setattr("kagent.agent.workspace.ROLLBACK_ROOT", str(tmp_path / "rollback"))
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path / "state"))
    db.init_db()

    def fake_create(**kwargs):
        callback = kwargs.get("on_request_event")
        if callback:
            callback(
                {
                    "type": "model_request",
                    "model": kwargs["model"],
                    "reasoning_effort": kwargs["reasoning_effort"],
                    "stream": kwargs["stream"],
                    "has_tools": bool(kwargs.get("tools")),
                }
            )
            callback(
                {
                    "type": "model_response",
                    "model": kwargs["model"],
                    "reasoning_effort": kwargs["reasoning_effort"],
                    "duration_ms": 12,
                }
            )
        return [_chunk(content="done")]

    monkeypatch.setattr("kagent.agent.code_agent.create_chat_completion_with_reasoning", fake_create)

    agent = CodeAgent(
        workspace_root=str(tmp_path),
        session_id="session-1",
        model="gpt-5.5",
        reasoning_effort="high",
    )
    agent.run([{"role": "user", "content": "finish"}], max_rounds=1)

    events = read_run_events(agent.run_logger.path)
    model_events = [event for event in events if event["event"].startswith("model_")]

    assert [event["event"] for event in model_events] == ["model_request", "model_response"]
    assert model_events[0]["data"]["model"] == "gpt-5.5"
    assert model_events[0]["data"]["reasoning_effort"] == "high"


def _chunk(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                )
            )
        ],
        close=lambda: None,
    )


def _tool_delta(call_id, name, arguments):
    return SimpleNamespace(
        index=0,
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )
