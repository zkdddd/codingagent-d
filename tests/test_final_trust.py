from kagent.agent.final_trust import build_final_trust_summary, final_trust_prompt


def test_final_trust_fails_unverified_changes():
    summary = build_final_trust_summary(
        status="completed",
        content_changed=True,
        changed_paths=["kagent/app.py"],
        validated=False,
        validation_failed=False,
    )

    assert summary["health"] == "fail"
    assert summary["trustworthy"] is False
    assert [issue["code"] for issue in summary["issues"]] == ["unverified_changes"]
    prompt = final_trust_prompt(summary)
    assert "unverified_changes" in prompt
    assert "Do not claim validation passed" in prompt


def test_final_trust_warns_for_recovered_tool_issues():
    summary = build_final_trust_summary(
        status="completed",
        content_changed=True,
        changed_paths=["kagent/app.py"],
        validated=True,
        validation_failed=False,
        failed_tool_count=1,
        loop_warning_count=1,
    )

    assert summary["health"] == "warn"
    assert [issue["code"] for issue in summary["issues"]] == [
        "failed_tools",
        "loop_warning",
    ]


def test_final_trust_passes_clean_validated_run():
    summary = build_final_trust_summary(
        status="completed",
        content_changed=True,
        changed_paths=["kagent/app.py"],
        validated=True,
        validation_failed=False,
    )

    assert summary["health"] == "pass"
    assert summary["trustworthy"] is True
    assert summary["issues"] == []


def test_final_trust_prompt_includes_symbol_impacts():
    summary = build_final_trust_summary(
        status="completed",
        content_changed=True,
        changed_paths=["kagent/agent/validation.py"],
        validated=True,
        validation_failed=False,
        symbol_impacts=[
            {
                "symbol": "build_validation_plan",
                "definition_path": "kagent/agent/validation.py",
                "reference_count": 12,
                "related_tests": ["tests/test_validation.py"],
            }
        ],
    )

    prompt = final_trust_prompt(summary)

    assert summary["symbol_impacts"][0]["symbol"] == "build_validation_plan"
    assert "symbol_impacts" in prompt
    assert "build_validation_plan at kagent/agent/validation.py" in prompt
    assert "tests/test_validation.py" in prompt


def test_final_trust_prompt_includes_quality_gate():
    summary = build_final_trust_summary(
        status="completed",
        content_changed=True,
        changed_paths=["kagent/app.py"],
        validated=True,
        validation_failed=False,
    )

    prompt = final_trust_prompt(summary)

    assert "quality_gate" in summary
    assert "quality_gate" in prompt
    assert "Include the quality gate result" in prompt
