from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_memory import build_project_memory

RULES_FILENAME = "KAGENT.md"
DEFAULT_RULES_MAX_CHARS = 12000
REQUIRED_SECTIONS = {
    "project_overview": ["project overview", "项目概览", "项目说明"],
    "coding_rules": ["coding rules", "代码规则", "编码规则"],
    "validation": ["validation", "验证", "测试"],
    "safety": ["safety", "安全"],
}


def load_project_rules(root: str | Path, *, max_chars: int = DEFAULT_RULES_MAX_CHARS) -> dict[str, Any]:
    project_root = Path(root).resolve()
    rules_path = project_root / RULES_FILENAME
    if not rules_path.exists():
        return {
            "ok": True,
            "exists": False,
            "path": RULES_FILENAME,
            "abs_path": str(rules_path),
            "content": "",
            "truncated": False,
        }
    if rules_path.is_dir():
        return {
            "ok": False,
            "exists": True,
            "path": RULES_FILENAME,
            "abs_path": str(rules_path),
            "content": "",
            "truncated": False,
            "error": f"{RULES_FILENAME} is a directory, expected a UTF-8 markdown file.",
        }

    try:
        content = rules_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return {
            "ok": False,
            "exists": True,
            "path": RULES_FILENAME,
            "abs_path": str(rules_path),
            "content": "",
            "truncated": False,
            "error": f"{RULES_FILENAME} is not valid UTF-8 text: {exc}",
        }

    clipped, truncated = _clip(content, max_chars)
    return {
        "ok": True,
        "exists": True,
        "path": RULES_FILENAME,
        "abs_path": str(rules_path),
        "content": clipped,
        "content_chars": len(content),
        "truncated": truncated,
    }


def format_project_rules_for_prompt(rules: dict[str, Any] | None) -> str:
    if not rules or not rules.get("exists"):
        return ""
    if not rules.get("ok"):
        return f"Project rules from {RULES_FILENAME} are unavailable: {rules.get('error') or 'unknown error'}"

    content = str(rules.get("content") or "").strip()
    if not content:
        return ""

    suffix = ""
    if rules.get("truncated"):
        suffix = "\n\n[Project rules were clipped for context. Read KAGENT.md directly before relying on omitted details.]"
    return (
        f"Project rules from {RULES_FILENAME}.\n"
        "Follow these explicit project rules unless the user directly overrides them.\n\n"
        f"{content}"
        f"{suffix}"
    )


def format_project_rules_health_for_prompt(check: dict[str, Any] | None) -> str:
    if not check or not check.get("ok"):
        error = check.get("error") if isinstance(check, dict) else "unknown error"
        return f"Project rules health check is unavailable: {error}"

    health = str(check.get("health") or "unknown")
    score = check.get("score")
    issues = check.get("issues") if isinstance(check.get("issues"), list) else []
    if health == "good" and not issues:
        return ""

    lines = [
        f"Project rules health check for {RULES_FILENAME}.",
        "Use this as a lightweight planning warning. Do not edit KAGENT.md unless the user asks or the current task is to maintain project rules.",
        f"- health: {health}",
    ]
    if score is not None:
        lines.append(f"- score: {score}")
    if issues:
        lines.append("- issues:")
        for issue in issues[:6]:
            if not isinstance(issue, dict):
                continue
            kind = issue.get("kind") or "issue"
            severity = issue.get("severity") or "unknown"
            message = issue.get("message") or ""
            suggestion = issue.get("suggestion") or ""
            line = f"  - {severity}: {kind}"
            if message:
                line += f" - {message}"
            if suggestion:
                line += f" Suggestion: {suggestion}"
            lines.append(line)

    additions = check.get("suggested_additions")
    if isinstance(additions, list) and additions:
        lines.append("- suggested_additions:")
        for addition in additions[:3]:
            text = str(addition).strip()
            if not text:
                continue
            lines.append("  - " + text.replace("\n", " ")[:500])
    return "\n".join(lines)


def generate_project_rules(root: str | Path, *, max_chars: int = DEFAULT_RULES_MAX_CHARS) -> dict[str, Any]:
    project_root = Path(root).resolve()
    memory = build_project_memory(project_root)
    summary = memory.get("project_summary") if isinstance(memory.get("project_summary"), dict) else {}
    validation_commands = memory.get("validation_commands")
    if not isinstance(validation_commands, list):
        validation_commands = []
    preferences = memory.get("preferences")
    if not isinstance(preferences, list):
        preferences = []

    lines = [
        "# KAGENT.md",
        "",
        "Project-level rules for KAgent. Keep this file short, concrete, and updated when the workflow changes.",
        "",
        "## Project Overview",
        "",
        f"- Workspace root: `{project_root}`",
        f"- Project type: `{memory.get('project_type') or 'generic'}`",
        f"- Source files: {summary.get('source_count', 0)}",
        f"- Test files: {summary.get('test_count', 0)}",
        f"- Source files with mapped tests: {summary.get('mapped_source_count', 0)}",
    ]
    entry_files = memory.get("entry_files") if isinstance(memory.get("entry_files"), list) else []
    config_files = memory.get("config_files") if isinstance(memory.get("config_files"), list) else []
    if entry_files:
        lines.append("- Common entry files: " + ", ".join(f"`{path}`" for path in entry_files[:10]))
    if config_files:
        lines.append("- Important config files: " + ", ".join(f"`{path}`" for path in config_files[:10]))

    lines.extend(
        [
            "",
            "## Coding Rules",
            "",
            "- Prefer small, reviewable edits over broad rewrites.",
            "- Inspect related symbols and tests before changing behavior.",
            "- Keep user-facing documentation updated when adding or optimizing a feature.",
            "- Preserve unrelated user changes in the working tree.",
            "",
            "## Validation",
            "",
        ]
    )
    if validation_commands:
        for item in validation_commands[:8]:
            if not isinstance(item, dict):
                continue
            command = item.get("command")
            if command:
                label = item.get("label") or "Validation"
                cwd = item.get("cwd") or "."
                lines.append(f"- {label}: `{command}` from `{cwd}`")
    else:
        lines.append("- Add the preferred test or verification command here.")

    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Do not run destructive git or filesystem commands unless the user explicitly asks.",
            "- Do not install dependencies or use network commands unless needed for the task.",
            "- Before risky edits, explain target files, reason, and validation plan.",
        ]
    )
    if preferences:
        lines.extend(["", "## Project Preferences", ""])
        for preference in preferences[:8]:
            lines.append(f"- {preference}")

    content, truncated = _clip("\n".join(lines).rstrip() + "\n", max_chars)
    return {
        "ok": True,
        "path": RULES_FILENAME,
        "abs_path": str(project_root / RULES_FILENAME),
        "content": content,
        "content_chars": len(content),
        "truncated": truncated,
        "write_hint": f"Review this draft, then write it to {RULES_FILENAME} if it matches the project workflow.",
    }


def check_project_rules(root: str | Path, *, max_chars: int = DEFAULT_RULES_MAX_CHARS) -> dict[str, Any]:
    rules = load_project_rules(root, max_chars=max_chars)
    if not rules.get("ok"):
        return {
            "ok": False,
            "exists": rules.get("exists", False),
            "path": RULES_FILENAME,
            "error": rules.get("error") or "Unable to read project rules.",
            "issues": [
                {
                    "kind": "read_error",
                    "severity": "high",
                    "message": rules.get("error") or "Unable to read project rules.",
                    "suggestion": f"Replace {RULES_FILENAME} with a UTF-8 markdown rules file.",
                }
            ],
            "suggested_additions": [],
        }
    if not rules.get("exists"):
        draft = generate_project_rules(root, max_chars=max_chars)
        return {
            "ok": True,
            "exists": False,
            "path": RULES_FILENAME,
            "health": "missing",
            "score": 0,
            "issues": [
                {
                    "kind": "missing_file",
                    "severity": "high",
                    "message": f"{RULES_FILENAME} does not exist.",
                    "suggestion": f"Create {RULES_FILENAME} from the generated draft after review.",
                }
            ],
            "suggested_additions": [draft["content"]],
            "draft": draft,
        }

    content = str(rules.get("content") or "")
    lower = content.lower()
    issues: list[dict[str, str]] = []
    suggested_additions: list[str] = []

    for key, aliases in REQUIRED_SECTIONS.items():
        if not any(alias in lower for alias in aliases):
            label = _section_label(key)
            issues.append(
                {
                    "kind": f"missing_{key}",
                    "severity": "medium",
                    "message": f"{RULES_FILENAME} is missing a {label} section.",
                    "suggestion": f"Add a '## {label}' section.",
                }
            )
            suggested_additions.append(_section_template(key, root))

    if "run-tests.bat" not in lower and "pytest" not in lower and "npm test" not in lower:
        issues.append(
            {
                "kind": "missing_validation_command",
                "severity": "high",
                "message": f"{RULES_FILENAME} does not mention a concrete validation command.",
                "suggestion": "Add the preferred targeted and full validation commands.",
            }
        )
        suggested_additions.append(_section_template("validation", root))

    if "readme.md" not in lower or "docs/agent-development.md" not in lower:
        issues.append(
            {
                "kind": "missing_documentation_rule",
                "severity": "medium",
                "message": f"{RULES_FILENAME} should mention README.md and docs/agent-development.md updates.",
                "suggestion": "Add a rule requiring docs updates for each feature or optimization.",
            }
        )
        suggested_additions.append(
            "- Document every feature or optimization in `README.md` and `docs/agent-development.md`."
        )

    if "preserve unrelated" not in lower and "unrelated user changes" not in lower:
        issues.append(
            {
                "kind": "missing_dirty_worktree_rule",
                "severity": "medium",
                "message": f"{RULES_FILENAME} should protect unrelated user changes.",
                "suggestion": "Add a rule to preserve unrelated user changes in the working tree.",
            }
        )
        suggested_additions.append("- Preserve unrelated user changes in the working tree.")

    high_count = sum(1 for issue in issues if issue.get("severity") == "high")
    medium_count = sum(1 for issue in issues if issue.get("severity") == "medium")
    score = max(0, 100 - high_count * 30 - medium_count * 15)
    health = "good" if score >= 85 else "needs_attention" if score >= 50 else "weak"
    return {
        "ok": True,
        "exists": True,
        "path": RULES_FILENAME,
        "health": health,
        "score": score,
        "issue_count": len(issues),
        "issues": issues,
        "suggested_additions": _dedupe_texts(suggested_additions),
        "truncated": rules.get("truncated", False),
    }


def _section_label(key: str) -> str:
    return {
        "project_overview": "Project Overview",
        "coding_rules": "Coding Rules",
        "validation": "Validation",
        "safety": "Safety",
    }.get(key, key.replace("_", " ").title())


def _section_template(key: str, root: str | Path) -> str:
    if key == "project_overview":
        return "## Project Overview\n\n- Describe the project purpose, main source directory, test directory, and important docs."
    if key == "coding_rules":
        return "## Coding Rules\n\n- Prefer small, reviewable edits.\n- Inspect related symbols and tests before changing behavior."
    if key == "validation":
        generated = generate_project_rules(root)
        content = str(generated.get("content") or "")
        start = content.find("## Validation")
        end = content.find("\n## Safety", start)
        if start >= 0 and end > start:
            return content[start:end].strip()
        return "## Validation\n\n- Run targeted tests first.\n- Run the full project validation command before finishing larger changes."
    if key == "safety":
        return "## Safety\n\n- Do not run destructive git or filesystem commands unless the user explicitly asks."
    return ""


def _dedupe_texts(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _clip(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    marker = "\n\n[... clipped ...]\n"
    keep = max(0, max_chars - len(marker))
    head = keep // 2
    tail = keep - head
    return text[:head].rstrip() + marker + text[-tail:].lstrip(), True
