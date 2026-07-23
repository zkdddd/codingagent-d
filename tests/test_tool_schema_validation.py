from __future__ import annotations

from kagent.agent.tool_schema import validate_tool_args


def test_valid_arguments_pass():
    assert validate_tool_args("list_files", {"path": ".", "max_results": 10}) == []
    assert validate_tool_args("search_file", {"query": "foo"}) == []
    assert validate_tool_args("write_file", {"path": "a.py", "content": "x"}) == []


def test_missing_required_field_fails():
    errors = validate_tool_args("search_file", {})
    assert errors
    assert "query" in errors[0]
    assert "required" in errors[0]


def test_wrong_type_fails():
    errors = validate_tool_args("list_files", {"path": 123})
    assert errors
    assert "path" in errors[0]
    assert "string" in errors[0]


def test_additional_property_rejected():
    errors = validate_tool_args("list_files", {"path": ".", "bogus_field": 1})
    assert errors
    assert any("Additional properties" in e or "bogus" in e for e in errors)


def test_unknown_tool_not_validated():
    # Adding a tool before wiring its schema must not block dispatch.
    assert validate_tool_args("does_not_exist", {"anything": 1}) == []


def test_non_dict_arguments_fail():
    errors = validate_tool_args("list_files", "not an object")
    assert errors
    assert "object" in errors[0]


def test_integer_constraint_enforced():
    # timeout_ms must be an integer, not a string.
    errors = validate_tool_args("run_command", {"command": "ls", "timeout_ms": "fast"})
    assert errors
    assert "timeout_ms" in errors[0]


def test_optional_fields_can_be_omitted():
    # list_files has no required field; empty object is valid.
    assert validate_tool_args("list_files", {}) == []
    # max_results has a maximum; within range is fine.
    assert validate_tool_args("list_files", {"max_results": 100}) == []


def test_max_constraint_enforced():
    # max_results maximum is 2000; above should fail.
    errors = validate_tool_args("list_files", {"max_results": 99999})
    assert errors
