from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def prepare_pytest_junit_command(
    command: str,
    *,
    workspace_root: str | Path,
    run_id: str,
    validation_run_seq: int,
    command_idx: int,
) -> dict[str, Any]:
    """Return a pytest command variant that emits JUnit XML when safe."""
    command_text = str(command or "").strip()
    if not _looks_like_direct_pytest(command_text) or _has_junitxml(command_text):
        return {"enabled": False, "command": command_text, "junit_xml_path": None}

    root = Path(workspace_root).resolve()
    junit_dir = root / ".kagent" / "test-results"
    junit_dir.mkdir(parents=True, exist_ok=True)
    safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(run_id or uuid.uuid4().hex))[:64]
    junit_path = junit_dir / f"{safe_run_id}-{validation_run_seq}-{command_idx}.xml"
    return {
        "enabled": True,
        "command": f'{command_text} --junitxml="{junit_path}"',
        "original_command": command_text,
        "junit_xml_path": str(junit_path),
    }


def normalize_pytest_command(command: str) -> str:
    command_text = str(command or "").strip()
    if not command_text:
        return ""
    command_text = re.sub(r"\s+--junitxml=(?:\"[^\"]+\"|'[^']+'|[^\s]+)", "", command_text)
    command_text = re.sub(r"\s+--junit-xml=(?:\"[^\"]+\"|'[^']+'|[^\s]+)", "", command_text)
    return " ".join(command_text.split())


def parse_junit_xml(path: str | Path) -> list[dict[str, Any]]:
    xml_path = Path(path)
    if not xml_path.exists() or not xml_path.is_file():
        return []
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return []

    cases: list[dict[str, Any]] = []
    for testcase in root.iter("testcase"):
        if not isinstance(testcase.tag, str):
            continue
        case = _testcase_result(testcase)
        if case:
            cases.append(case)
    return cases


def _testcase_result(testcase: ET.Element) -> dict[str, Any] | None:
    classname = str(testcase.attrib.get("classname") or "").strip()
    name = str(testcase.attrib.get("name") or "").strip()
    file_path = str(testcase.attrib.get("file") or "").strip().replace("\\", "/")
    if not name and not classname:
        return None

    status = "passed"
    message = ""
    failure_type = ""
    for child in list(testcase):
        tag = _strip_namespace(child.tag)
        if tag in {"failure", "error", "skipped"}:
            status = "failed" if tag == "failure" else tag
            message = str(child.attrib.get("message") or child.text or "").strip()
            failure_type = str(child.attrib.get("type") or tag).strip()
            break

    return {
        "nodeid": _nodeid(classname=classname, name=name, file_path=file_path),
        "status": status,
        "duration_ms": _duration_ms(testcase.attrib.get("time")),
        "message": message,
        "failure_type": failure_type,
        "file": file_path,
        "classname": classname,
        "name": name,
    }


def _looks_like_direct_pytest(command: str) -> bool:
    normalized = command.strip().lower()
    if not normalized:
        return False
    if "pytest" not in normalized:
        return False
    script_indicators = ("run-tests", "verify.ps1", ".bat", ".ps1", "npm ", "pnpm ", "yarn ")
    if any(indicator in normalized for indicator in script_indicators):
        return False
    return bool(
        re.search(r"(^|\s)pytest(\.exe)?(\s|$)", normalized)
        or re.search(r"(^|\s)python(\.exe)?\s+-m\s+pytest(\s|$)", normalized)
        or re.search(r"(^|\s)py\s+-m\s+pytest(\s|$)", normalized)
    )


def _has_junitxml(command: str) -> bool:
    return "--junitxml" in command.lower()


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _duration_ms(raw: Any) -> int:
    try:
        return max(0, int(float(raw or 0) * 1000))
    except (TypeError, ValueError):
        return 0


def _nodeid(*, classname: str, name: str, file_path: str) -> str:
    if file_path:
        return f"{file_path}::{name}" if name else file_path
    module_path = classname.replace(".", "/").strip("/")
    if module_path and not module_path.endswith(".py"):
        module_path += ".py"
    if module_path and name:
        return f"{module_path}::{name}"
    return name or classname
