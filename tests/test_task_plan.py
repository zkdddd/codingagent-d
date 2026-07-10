from kagent.agent.task_plan import (
    build_task_plan,
    next_plan_action,
    plan_for_model,
    plan_progress_snapshot,
    plan_summary_text,
    plan_to_dicts,
    set_plan_step,
)


def test_build_task_plan_for_code_edit_includes_inspect_edit_validate():
    plan = build_task_plan(
        "修改代码并验证",
        requires_tools=True,
        requires_code_edit=True,
    )

    assert [step.step_id for step in plan] == [
        "understand_task",
        "inspect_context",
        "make_changes",
        "validate_changes",
        "final_answer",
    ]
    assert plan[0].status == "done"
    assert plan[1].status == "active"


def test_build_task_plan_for_chat_answer_activates_final_answer():
    plan = build_task_plan(
        "解释一下这个概念",
        requires_tools=False,
        requires_code_edit=False,
    )

    assert [step.step_id for step in plan] == ["understand_task", "final_answer"]
    assert plan[1].status == "active"


def test_set_plan_step_updates_status_and_detail():
    plan = build_task_plan("检查文件", requires_tools=True, requires_code_edit=False)

    changed = set_plan_step(plan, "inspect_context", "done", "Read relevant files")

    assert changed is True
    assert plan[1].status == "done"
    assert plan[1].detail == "Read relevant files"


def test_plan_serialization_and_model_prompt():
    plan = build_task_plan("修复 bug", requires_tools=True, requires_code_edit=True)

    serialized = plan_to_dicts(plan)
    prompt = plan_for_model(plan)
    summary = plan_summary_text(plan)

    assert serialized[0]["id"] == "understand_task"
    assert "Execution checklist" in prompt
    assert "validate_changes=pending" in summary


def test_task_plan_includes_decomposition_metadata():
    plan = build_task_plan(
        "Update kagent/agent/context.py and tests/test_context.py",
        requires_tools=True,
        requires_code_edit=True,
    )

    serialized = plan_to_dicts(plan)
    make_changes = serialized[2]
    validate = serialized[3]
    prompt = plan_for_model(plan)

    assert make_changes["objective"] == "Apply focused, reviewable edits that satisfy the requested feature or fix."
    assert make_changes["files"] == ["kagent/agent/context.py", "tests/test_context.py"]
    assert "behavior regression" in make_changes["risks"]
    assert "run related tests before full validation" in validate["validation"]
    assert "objective:" in prompt
    assert "files: kagent/agent/context.py, tests/test_context.py" in prompt


def test_plan_progress_snapshot_reports_next_action():
    plan = build_task_plan(
        "Implement validation command learning",
        requires_tools=True,
        requires_code_edit=True,
    )
    set_plan_step(plan, "inspect_context", "done", "Read existing validation code")

    snapshot = plan_progress_snapshot(plan)
    next_action = next_plan_action(plan)

    assert snapshot["total"] == 5
    assert snapshot["counts"]["done"] == 2
    assert next_action["id"] == "make_changes"
    assert next_action["status"] == "pending"
