from kagent.agent.code_agent import AgentRunState, CodeAgent
from kagent.agent.run_log import RunLogger, read_run_events
from kagent.agent.test_telemetry import (
    normalize_pytest_command,
    parse_junit_xml,
    prepare_pytest_junit_command,
)


def test_parse_junit_xml_extracts_per_test_results(tmp_path):
    xml_path = tmp_path / "junit.xml"
    xml_path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="3" failures="1" errors="0" skipped="1">
    <testcase classname="tests.test_sample" name="test_pass" time="0.012" />
    <testcase classname="tests.test_sample" name="test_fail" time="0.034">
      <failure message="assert 1 == 2">AssertionError</failure>
    </testcase>
    <testcase classname="tests.test_sample" name="test_skip" time="0.001">
      <skipped message="not now" />
    </testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )

    cases = parse_junit_xml(xml_path)

    assert [case["status"] for case in cases] == ["passed", "failed", "skipped"]
    assert cases[0]["nodeid"] == "tests/test_sample.py::test_pass"
    assert cases[1]["duration_ms"] == 34
    assert cases[1]["message"] == "assert 1 == 2"


def test_prepare_pytest_junit_command_only_wraps_direct_pytest(tmp_path):
    prepared = prepare_pytest_junit_command(
        "python -m pytest -q tests/test_sample.py",
        workspace_root=tmp_path,
        run_id="run-1",
        validation_run_seq=2,
        command_idx=3,
    )

    assert prepared["enabled"] is True
    assert "--junitxml=" in prepared["command"]
    assert "python -m pytest -q tests/test_sample.py" in prepared["command"]
    assert str(tmp_path / ".kagent" / "test-results") in prepared["junit_xml_path"]

    script = prepare_pytest_junit_command(
        "run-tests.bat",
        workspace_root=tmp_path,
        run_id="run-1",
        validation_run_seq=1,
        command_idx=1,
    )

    assert script["enabled"] is False
    assert script["command"] == "run-tests.bat"


def test_normalize_pytest_command_removes_junitxml_argument():
    assert (
        normalize_pytest_command('python -m pytest -q tests --junitxml="C:/tmp/result.xml"')
        == "python -m pytest -q tests"
    )
    assert (
        normalize_pytest_command("pytest -q --junit-xml=C:/tmp/result.xml")
        == "pytest -q"
    )


def test_auto_validation_writes_test_case_result_events(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(state_dir))

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )

    agent = CodeAgent(workspace_root=str(tmp_path), session_id="session-1")
    agent.run_logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    state = AgentRunState(changed_paths={"tests/test_sample.py"})
    plan = {
        "summary": "Run telemetry pytest",
        "commands": [
            {
                "label": "Related tests",
                "command": "python -m pytest -q tests/test_sample.py",
                "cwd": ".",
                "timeout_ms": 120000,
            }
        ],
    }

    ok, summary, executed = agent._run_auto_validation(
        plan=plan,
        validation_run_seq=1,
        round_idx=1,
        state=state,
        messages=[],
        report_parts=[],
        emit=None,
        on_event=None,
        symbol_plans=[],
    )

    events = read_run_events(agent.run_logger.path)
    telemetry_events = [event for event in events if event["event"] == "test_case_telemetry"]
    case_events = [event for event in events if event["event"] == "test_case_result"]

    assert ok is True
    assert executed == 1
    assert summary
    assert telemetry_events[0]["data"]["case_count"] == 1
    assert case_events[0]["data"]["nodeid"].endswith("::test_ok")
    assert case_events[0]["data"]["status"] == "passed"
