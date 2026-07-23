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


def test_final_trust_quality_gate_checks_aligned_with_run_review():
    """The runtime gate check codes should match run_review's richer gate so the
    gate shown in run history / run_analytics trends is consistent with the
    post-hoc review gate in naming and meaning."""
    from kagent.agent.run_review import build_run_review, build_quality_gate
    from kagent.agent.run_log import RunLogger
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    log = RunLogger(session_id="s", workspace_root=str(tmp))
    log.finish("completed", {"validated": True, "changed_paths": ["kagent/app.py"]})
    review = build_run_review(log.path)
    review_gate_codes = {c["code"] for c in build_quality_gate(review)["checks"]}

    summary = build_final_trust_summary(
        status="completed",
        content_changed=True,
        changed_paths=["kagent/app.py"],
        validated=True,
        validation_failed=False,
    )
    runtime_gate_codes = {c["code"] for c in summary["quality_gate"]["checks"]}

    # The runtime gate's codes must be a subset of (and aligned with) the review gate.
    assert runtime_gate_codes.issubset(review_gate_codes)
    # Core checks present in both.
    assert {"run_completed", "changes_validated", "validation_passed"}.issubset(runtime_gate_codes)
    # The legacy misaligned codes are gone.
    assert "trustworthy" not in runtime_gate_codes
    assert "validation_recorded" not in runtime_gate_codes
    assert "validation_result" not in runtime_gate_codes


def test_final_trust_warns_on_coverage_regression():
    summary = build_final_trust_summary(
        status="completed",
        content_changed=True,
        changed_paths=["kagent/app.py"],
        validated=True,
        validation_failed=False,
        coverage_gate={
            "status": "warn",
            "message": "coverage dropped 5.0% (80.0% -> 75.0%)",
            "recent_line_rate": 0.75,
            "baseline_line_rate": 0.80,
            "delta": -0.05,
        },
    )

    gate = summary["quality_gate"]
    assert gate["status"] == "warn"
    codes = [c["code"] for c in gate["checks"]]
    assert "coverage_regression" in codes
    coverage_check = next(c for c in gate["checks"] if c["code"] == "coverage_regression")
    assert "dropped" in coverage_check["message"]


def test_final_trust_ignores_coverage_gate_without_history():
    summary = build_final_trust_summary(
        status="completed",
        content_changed=True,
        changed_paths=["kagent/app.py"],
        validated=True,
        validation_failed=False,
        coverage_gate=None,
    )

    codes = [c["code"] for c in summary["quality_gate"]["checks"]]
    assert "coverage_regression" not in codes
    assert summary["quality_gate"]["status"] == "pass"
