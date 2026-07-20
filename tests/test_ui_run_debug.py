from kagent.agent.run_log import RunLogger
from kagent.ui.main_window import (
    _activity_recent_path_lines,
    _activity_recent_resume_lines,
    _activity_status_summary,
    _diff_review_markdown,
    _resume_history_candidates,
    _resume_history_item_label,
    _resume_history_markdown,
    _resume_task_prompt,
    _run_debug_markdown,
    _plan_steps_summary,
    _project_quick_prompts,
    _recent_workspace_roots,
    _session_workspace_summary,
    _session_title_for_workspace,
    _slash_command_matches,
    _slash_commands,
    _tool_entry_actions,
    _tool_event_markdown,
    _t,
    _workspace_button_label,
    _tool_event_summary,
)


def test_run_debug_markdown_includes_summary_and_self_check(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("tool_call", {"name": "read_file"})
    logger.finish("completed", {"validated": True, "changed_paths": []})

    markdown = _run_debug_markdown(str(logger.path), "summary")

    assert "运行摘要" in markdown
    assert "自检结果" in markdown
    assert "health: pass" in markdown
    assert "tools: read_file x1" in markdown


def test_run_debug_markdown_includes_run_review_report(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("run_context", {"task": "Add run review UI"})
    logger.write("model_request", {"model": "gpt-5.5", "reasoning_effort": "medium"})
    logger.finish("completed", {"validated": True, "changed_paths": ["kagent/ui/main_window.py"]})

    markdown = _run_debug_markdown(str(logger.path), "review")

    assert "# Run Review" in markdown
    assert "Add run review UI" in markdown
    assert "`kagent/ui/main_window.py`" in markdown
    assert "model_request: `gpt-5.5`/`medium` x1" in markdown


def test_run_debug_markdown_includes_bug_report_and_regression_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("run_context", {"task": "Fix validation failure"})
    logger.write("tool_result", {"name": "run_command", "ok": False, "error": "pytest failed"})
    logger.finish(
        "completed",
        {
            "validated": False,
            "validation_failed": True,
            "changed_paths": ["kagent/ui/main_window.py"],
            "last_validation_summary": "1 failed",
        },
    )

    gate = _run_debug_markdown(str(logger.path), "quality_gate")
    bug = _run_debug_markdown(str(logger.path), "bug_report")
    plan = _run_debug_markdown(str(logger.path), "regression_plan")

    assert "# Quality Gate" in gate
    assert "[fail] `changes_validated`" in gate
    assert "# Bug Report" in bug
    assert "Validation failure after: Fix validation failure" in bug
    assert "# Regression Test Plan" in plan
    assert "`kagent/ui/main_window.py`" in plan


def test_run_debug_markdown_includes_project_rules_health(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write(
        "project_rules_check",
        {
            "path": "KAGENT.md",
            "health": "weak",
            "score": 40,
            "issue_count": 2,
            "issues": [
                {"kind": "missing_validation_command", "severity": "high"},
                {"kind": "missing_safety", "severity": "medium"},
            ],
        },
    )
    logger.finish("completed")

    summary = _run_debug_markdown(str(logger.path), "summary")
    timeline = _run_debug_markdown(str(logger.path), "timeline")

    assert "project_rules: weak, score 40, 2 issue(s)" in summary
    assert "Project rules: weak score 40" in timeline
    assert "high:missing_validation_command, medium:missing_safety" in timeline


def test_run_debug_markdown_includes_timeline(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.write("agent_status", {"phase": "planning", "detail": "Planning"})
    logger.finish("completed")

    markdown = _run_debug_markdown(str(logger.path), "timeline")

    assert "运行时间线" in markdown
    assert "Run started" in markdown
    assert "Phase: planning" in markdown
    assert "Planning" in markdown


def test_diff_review_markdown_includes_active_paths_and_preview(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    markdown = _diff_review_markdown(
        {
            "available": True,
            "summary": "2 active rollbackable paths",
            "paths": ["kagent/a.py", "tests/test_a.py"],
            "preview": "diff --git a/kagent/a.py b/kagent/a.py\n@@ -1 +1 @@\n-old\n+new\n",
        }
    )

    assert "当前差异审查" in markdown
    assert "**状态**: 可用" in markdown
    assert "`kagent/a.py`" in markdown
    assert "```diff" in markdown
    assert "+new" in markdown


def test_diff_review_markdown_handles_empty_preview(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    markdown = _diff_review_markdown({"available": False, "paths": []})

    assert "**状态**: 空" in markdown
    assert "当前会话没有可回滚的活跃变更" in markdown


def test_resume_task_prompt_wraps_context_for_agent(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    prompt = _resume_task_prompt(
        {
            "run_id": "run-1",
            "status": "stopped",
            "health": "warn",
            "priority": "continue_incomplete_plan",
            "resume_prompt": "Continue from the next unfinished plan step.",
        }
    )

    assert "继续上一次 Agent 任务" in prompt
    assert "run_id: run-1" in prompt
    assert "priority: continue_incomplete_plan" in prompt
    assert "Continue from the next unfinished plan step." in prompt


def test_resume_history_candidates_filter_problem_runs_by_workspace(tmp_path):
    rows = [
        {
            "run_id": "pass-run",
            "status": "completed",
            "health": "pass",
            "workspace_root": str(tmp_path),
            "failed_tool_count": 0,
        },
        {
            "run_id": "validation-run",
            "status": "completed",
            "health": "fail",
            "workspace_root": str(tmp_path),
            "validation_failed": True,
            "failed_tool_count": 0,
        },
        {
            "run_id": "other-workspace-run",
            "status": "stopped",
            "health": "fail",
            "workspace_root": str(tmp_path / "other"),
            "failed_tool_count": 0,
        },
        {
            "run_id": "gate-run",
            "status": "completed",
            "health": "pass",
            "workspace_root": str(tmp_path),
            "quality_gate_status": "fail",
            "failed_tool_count": 0,
        },
    ]

    candidates = _resume_history_candidates(rows, workspace_root=str(tmp_path))

    assert [item["run_id"] for item in candidates] == ["validation-run", "gate-run"]


def test_resume_history_item_label_and_markdown(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    label = _resume_history_item_label(
        {
            "run_id": "abcdef123456",
            "started_at": "2026-07-13T10:00:00Z",
            "status": "completed",
            "health": "fail",
            "validation_failed": True,
            "failed_tool_count": 2,
            "quality_gate_status": "warn",
        }
    )
    markdown = _resume_history_markdown(
        {
            "run_id": "abcdef123456",
            "status": "completed",
            "health": "fail",
            "priority": "fix_validation_failure",
            "resume_prompt": "Fix validation first.",
        }
    )

    assert "validation_failed" in label
    assert "failed_tools:2" in label
    assert "gate:warn" in label
    assert "abcdef1234" in label
    assert "Resume Preview" in markdown
    assert "fix_validation_failure" in markdown


def test_resume_history_markdown_can_include_related_diff(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    markdown = _resume_history_markdown(
        {
            "run_id": "run-1",
            "status": "completed",
            "health": "fail",
            "priority": "run_validation",
            "resume_prompt": "Validate changed files.",
        },
        {
            "available": True,
            "summary": "Previewing rollback for 1 path",
            "paths": ["kagent/app.py"],
            "preview": "diff --git a/kagent/app.py b/kagent/app.py\n@@ -1 +1 @@\n-old\n+new\n",
        },
    )

    assert "Resume Preview" in markdown
    assert "Related Diff" in markdown
    assert "`kagent/app.py`" in markdown
    assert "+new" in markdown


def test_resume_prompt_editor_labels_follow_language(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    assert _t("resume_prompt_editor") == "Resume prompt (editable)"
    assert _t("copy_resume_prompt") == "Copy prompt"

    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    assert _t("resume_prompt_editor")
    assert _t("copy_resume_prompt")


def test_activity_entry_tooltips_distinguish_diff_resume_and_history(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    assert _t("activity") == "Activity"
    assert _t("activity_title") == "Activity Panel"
    assert _t("activity_back") == "Back"
    assert _t("activity_back_to_activity") == "Back to Activity"
    assert "one place" in _t("activity_tip")
    assert "together" in _t("activity_intro")
    assert "current session" in _t("diff_review_tip")
    assert "previous run" in _t("resume_history_tip")
    assert "rollback records" in _t("rollback_history_tip")

    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    assert _t("activity")
    assert _t("activity_title")
    assert _t("activity_back")
    assert _t("activity_back_to_activity")
    assert _t("activity_tip")
    assert _t("activity_intro")
    assert _t("diff_review_tip")
    assert _t("resume_history_tip")
    assert _t("rollback_history_tip")


def test_activity_status_summary_handles_counts_and_empty_states(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    assert _activity_status_summary("diff", count=0) == "No rollbackable changes"
    assert _activity_status_summary("resume", count=2) == "2 run(s) need attention"
    assert _activity_status_summary("rollback", count=3) == "3 rollback record(s)"
    assert _activity_status_summary("diff", unavailable=True) == "Status unavailable"

    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    assert _activity_status_summary("diff", count=0)
    assert _activity_status_summary("resume", count=2)
    assert _activity_status_summary("rollback", count=3)


def test_activity_recent_resume_lines_show_recent_problem_runs(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    rows = [
        {
            "run_id": "run-1111111111",
            "started_at": "2026-07-15T10:00:00Z",
            "status": "completed",
            "health": "fail",
            "validation_failed": True,
            "failed_tool_count": 1,
        },
        {
            "run_id": "run-2222222222",
            "started_at": "2026-07-15T09:00:00Z",
            "status": "stopped",
            "health": "warn",
            "failed_tool_count": 0,
        },
    ]

    lines = _activity_recent_resume_lines(rows, limit=1)

    assert len(lines) == 1
    assert "validation_failed" in lines[0]
    assert "failed_tools:1" in lines[0]
    assert "run-111111" in lines[0]
    assert _activity_recent_resume_lines([]) == ["No recent runs need resume."]


def test_activity_recent_path_lines_limits_changed_paths(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    lines = _activity_recent_path_lines(
        ["kagent/ui/main_window.py", "tests/test_ui_run_debug.py", "README.md", "docs/log.md"],
        limit=2,
    )

    assert lines == [
        "`kagent/ui/main_window.py`",
        "`tests/test_ui_run_debug.py`",
        "+2 more",
    ]
    assert _activity_recent_path_lines([]) == ["No changed paths to show."]


def test_slash_commands_include_self_improvement_prompt(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    commands = _slash_commands()
    matches = _slash_command_matches("/self")

    assert any(command["name"] == "/self" for command in commands)
    assert [command["name"] for command in matches] == ["/self"]
    assert "suggest_self_improvements" in matches[0]["prompt"]
    assert _slash_command_matches("self") == []


def test_slash_commands_include_model_switches(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    top_level = _slash_command_matches("/")
    model_entry = _slash_command_matches("/model")
    model_matches = _slash_command_matches("/model ")
    model_values = [command.get("model") for command in model_matches]
    labels = [command.get("name") for command in model_matches]

    assert [command["name"] for command in top_level] == [
        "/self",
        "/check",
        "/test",
        "/explain",
        "/model",
        "/reasoning",
    ]
    assert model_entry[0]["action"] == "open_model_menu"
    assert "gpt-5.5" in model_values
    assert "gpt-5.4" in model_values
    assert "gpt-5.4-mini" in model_values
    assert "gpt-5.3-codex" in model_values
    assert "gpt-5.2" in model_values
    assert "/model GPT-5.5" in labels
    assert all(command.get("action") == "set_model" for command in model_matches)


def test_slash_commands_include_reasoning_switches(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    reasoning_entry = _slash_command_matches("/reasoning")
    reasoning_matches = _slash_command_matches("/reasoning ")
    efforts = [command.get("reasoning_effort") for command in reasoning_matches]
    labels = [command.get("name") for command in reasoning_matches]

    assert reasoning_entry[0]["action"] == "open_reasoning_menu"
    assert efforts == ["low", "medium", "high", "xhigh"]
    assert "/reasoning Low" in labels
    assert "/reasoning Medium" in labels
    assert "/reasoning High" in labels
    assert "/reasoning Extra high" in labels
    assert all(command.get("action") == "set_reasoning" for command in reasoning_matches)


def test_ui_markdown_uses_english_language(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    monkeypatch.setattr("kagent.agent.run_log.STATE_DIR", str(tmp_path))

    logger = RunLogger(session_id="session-1", workspace_root=str(tmp_path))
    logger.finish("completed", {"validated": True})

    debug = _run_debug_markdown(str(logger.path), "summary")
    diff = _diff_review_markdown({"available": False, "paths": []})
    prompt = _resume_task_prompt({"run_id": "run-1", "priority": "continue_next_plan_step"})

    assert "Run Summary" in debug
    assert "Self Check" in debug
    assert "**Status**: empty" in diff
    assert "No active rollbackable changes" in diff
    assert "Continue the previous Agent task" in prompt


def test_tool_options_use_selected_language(monkeypatch):
    result = {"entries": [{"rollback_id": 7, "available": True}]}

    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    zh_actions = _tool_entry_actions("list_rollback_history", result=result)
    zh_markdown = _tool_event_markdown("read_file", status="执行中", args={"path": "README.md"})

    assert zh_actions[0]["label"] == "差异 #7"
    assert "只展示差异预览" in zh_actions[0]["prompt"]
    assert "**状态** 执行中" in zh_markdown
    assert "**输入**" in zh_markdown

    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    en_actions = _tool_entry_actions("list_rollback_history", result=result)
    en_markdown = _tool_event_markdown("read_file", status="Running", args={"path": "README.md"})

    assert en_actions[0]["label"] == "Diff #7"
    assert "Show the diff preview only" in en_actions[0]["prompt"]
    assert "**Status** Running" in en_markdown
    assert "**Input**" in en_markdown


def test_tool_event_summary_handles_project_rules_health():
    summary = _tool_event_summary(
        "KAGENT.md rules",
        "Failed",
        result={"health": "weak", "score": 40, "issue_count": 2},
    )

    assert summary == "health weak, score 40, 2 issue(s)"


def test_session_title_for_workspace_uses_folder_name(tmp_path):
    project = tmp_path / "target-project"
    project.mkdir()

    assert _session_title_for_workspace(project) == "target-project"


def test_session_workspace_summary_distinguishes_project_and_no_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    project = tmp_path / "target-project"
    project.mkdir()

    project_summary = _session_workspace_summary(
        {
            "workspace_root": str(project),
            "created_at": "2026-07-13 09:30:00",
        },
        current=True,
    )
    no_folder_summary = _session_workspace_summary({"workspace_root": "", "created_at": ""})

    assert "target-project" in project_summary
    assert "Created 07-13 09:30" in project_summary
    assert "Current" in project_summary
    assert no_folder_summary == "Normal chat · No file access"


def test_workspace_button_label_shows_current_project_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    project = tmp_path / "target-project"
    project.mkdir()

    assert _workspace_button_label(project) == "当前项目：target-project"


def test_new_chat_label_distinguishes_normal_chat_from_folder_picker(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "zh")
    assert _t("new_chat") == "+  新增会话"
    assert _t("new_chat_for_folder") == "+  新建项目会话"
    assert _t("clear_workspace") == "不选择文件夹"

    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    assert _t("new_chat") == "+  New chat"
    assert _t("new_chat_for_folder") == "+  New project chat"
    assert _t("clear_workspace") == "No folder"


def test_empty_state_prompt_labels_follow_language(monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")

    assert _t("prompt_check_project") == "Check project"
    assert _t("prompt_fix_tests") == "Fix tests"
    assert _t("prompt_explain_project") == "Explain project"
    assert "project structure" in _t("prompt_check_project_text")


def test_recent_workspace_roots_deduplicates_existing_paths(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    roots = _recent_workspace_roots(
        [
            {"workspace_root": str(first)},
            {"workspace_root": str(first)},
            {"workspace_root": ""},
            {"workspace_root": str(second)},
            {"workspace_root": str(tmp_path / "missing")},
        ]
    )

    assert roots == [str(first.resolve()), str(second.resolve())]


def test_project_quick_prompts_include_entry_file_context(tmp_path, monkeypatch):
    monkeypatch.setattr("kagent.config.APP_LANGUAGE", "en")
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")

    prompts = _project_quick_prompts(str(tmp_path))

    assert [item["label"] for item in prompts] == ["Run tests", "Find TODOs", "Read entry files"]
    assert "main.py" in prompts[2]["prompt"]


def test_plan_steps_summary_marks_statuses():
    lines = _plan_steps_summary(
        [
            {"title": "Inspect", "status": "done"},
            {"title": "Edit", "status": "active", "detail": "Updating UI"},
            {"title": "Validate", "status": "pending"},
        ]
    )

    assert lines[0].startswith("✓ Inspect")
    assert "● Edit" in lines[1]
    assert "Updating UI" in lines[1]
    assert lines[2].startswith("○ Validate")
