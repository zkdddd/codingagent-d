import html
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QEvent, QPoint, Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QFontMetrics, QKeySequence, QShortcut, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from dotenv import set_key

from .. import config as app_config
from .. import db
from ..agent import WorkspaceTools
from ..agent.project_map import build_project_map, summarize_project_map
from ..agent.run_analytics import build_run_analytics, format_run_analytics_markdown
from ..agent.run_history import list_run_history
from ..agent.run_log_viewer import run_log_timeline, summarize_run_for_display
from ..agent.run_review import (
    build_run_review,
    format_quality_gate_markdown,
    format_bug_report_markdown,
    format_regression_plan_markdown,
    format_run_review_markdown,
)
from ..agent.run_self_check import format_run_health_report
from ..agent.task_resume import build_latest_resume_context, build_resume_context, format_resume_context
from ..config import (
    MODEL,
    REASONING_EFFORT,
    available_models,
    available_reasoning_efforts,
    model_display_name,
    normalize_reasoning_effort,
)
from ..ui_preferences import load_ui_preferences, save_ui_preferences
from .agent_worker import AgentWorker
from .markdown_view import highlight_css, render

THINKING_PLACEHOLDER_DELAY_MS = 220
WORKER_STOP_GRACE_MS = 1500


C_BG_ROOT = "#05070D"
C_BG_PANEL = "#080D16"
C_BG_PANEL_ALT = "#0B1220"
C_BG_SIDEBAR = "#070B12"
C_BG_SURFACE = "#0D1522"
C_BG_SURFACE_ALT = "#111C2D"
C_BG_INPUT = "#0B1220"
C_BG_INPUT_WRAP = "#0D1624"
C_TEXT_MAIN = "#EEF2F7"
C_TEXT_SUB = "#9AA8BA"
C_TEXT_PLACEHOLDER = "#66758A"
C_BORDER = "#1A2535"
C_BORDER_SOFT = "#121C2A"
C_ACCENT = "#38BDF8"
C_ACCENT_HOVER = "#0EA5E9"
C_ACCENT_2 = "#14B8A6"
C_USER_ACCENT = "#38BDF8"
C_ERROR = "#F87171"
C_RADIUS_SM = 10
C_RADIUS_MD = 12
C_RADIUS_LG = 16
C_RADIUS_XL = 22


UI_TEXT = {
    "zh": {
        "settings": "权限",
        "settings_title": "设置",
        "settings_heading": "应用设置",
        "language": "语言",
        "language_zh": "中文",
        "language_en": "英文",
        "read_scope": "读取范围",
        "write_scope": "写入范围",
        "command_scope": "命令范围",
        "extra_write_roots": "额外写入目录",
        "extra_command_roots": "额外命令目录",
        "settings_hint": "workspace 表示仅允许工作区和额外目录；all 表示允许整个文件系统。",
        "browse": "选择",
        "save": "保存",
        "cancel": "取消",
        "select_allowed_directory": "选择允许访问的目录",
        "path_placeholder": "Windows 下多个路径用 ; 分隔",
        "settings_busy": "请等待当前 agent 任务结束后再修改设置。",
        "settings_saved": "设置已更新。",
        "permissions": "权限",
        "permissions_saved": "权限已更新。",
        "read_permission": "读取",
        "write_permission": "写入",
        "command_permission": "命令",
        "workspace_scope": "工作区",
        "all_scope": "全部",
        "refresh": "刷新",
        "open_in_chat": "在聊天中打开",
        "restore": "恢复",
        "history": "历史",
        "diff_review": "差异",
        "resume_history": "恢复历史",
        "diff_review_tip": "查看当前会话可回滚变更汇总，用于快速审查本轮代码改动。",
        "resume_history_tip": "从历史 run log 中选择需要继续的任务，并可编辑恢复提示后提交。",
        "rollback_history_tip": "查看逐条 rollback 记录，预览版本差异或恢复指定版本。",
        "activity": "活动",
        "activity_title": "活动面板",
        "activity_tip": "集中查看当前差异、恢复历史任务和 rollback 历史。",
        "activity_intro": "把代码审查、任务恢复和版本回滚入口集中在一个地方，避免顶部出现重复按钮。",
        "activity_back": "返回",
        "activity_back_to_activity": "返回 Activity",
        "activity_open_diff": "查看当前差异",
        "activity_open_resume": "恢复历史任务",
        "activity_open_history": "打开回滚历史",
        "activity_open_analytics": "查看运行趋势",
        "activity_status_unavailable": "状态不可用",
        "activity_diff_clean": "当前没有可回滚改动",
        "activity_diff_count": "{count} 个当前改动文件",
        "activity_diff_recent_empty": "当前没有可展示的改动文件。",
        "activity_more_items": "+{count} more",
        "activity_resume_clean": "没有需要恢复的运行",
        "activity_resume_count": "{count} 个运行需要关注",
        "activity_resume_recent_empty": "最近没有需要恢复的运行。",
        "activity_rollback_clean": "没有 rollback 历史",
        "activity_rollback_count": "{count} 条 rollback 记录",
        "activity_analytics_empty": "没有可分析的运行记录",
        "activity_analytics_summary": "{runs} 次运行，{problems} 次需要关注",
        "run_analytics_tip": "汇总最近运行的质量门禁、验证失败、未验证变更、失败工具和模型错误趋势。",
        "run_analytics_title": "运行趋势分析",
        "workspace": "工作区",
        "switch_workspace": "切换工作区",
        "select_workspace": "选择工作区",
        "workspace_changed": "当前会话工作区已更新。",
        "workspace_missing": "工作区不存在：{path}",
        "workspace_label": "工作区：{path}",
        "workspace_button_label": "当前项目：{name}",
        "workspace_button_tooltip": "点击切换当前会话的目标项目：{path}",
        "new_chat": "+  新增会话",
        "new_chat_for_folder": "+  新建项目会话",
        "select_workspace_for_new_chat": "选择新会话的工作区",
        "clear_workspace": "不选择文件夹",
        "no_project": "未选择项目",
        "no_project_label": "项目：未选择",
        "no_project_tooltip": "当前会话未绑定项目，将作为普通聊天使用。",
        "no_project_for_workspace_action": "当前会话没有绑定项目，请先选择项目。",
        "no_project_chat_mode": "普通聊天",
        "no_project_chat_detail": "不访问文件",
        "project_chat_mode": "项目会话",
        "session_current_marker": "当前",
        "session_created_at": "创建于 {time}",
        "prompt_check_project": "检查项目结构",
        "prompt_fix_tests": "修复测试失败",
        "prompt_explain_project": "解释这个项目",
        "prompt_check_project_text": "请检查当前项目结构，说明主要模块、入口文件、测试入口，以及下一步建议。",
        "prompt_fix_tests_text": "请运行项目测试，定位失败原因并修复，最后告诉我修改内容和验证结果。",
        "prompt_explain_project_text": "请解释当前项目的功能、代码结构、运行方式和主要风险点。",
        "command_palette": "命令面板",
        "command_palette_placeholder": "输入命令，例如：切换项目 / 新建会话 / 查看差异",
        "command_new_chat": "新增会话",
        "command_new_project_chat": "新建项目会话",
        "command_switch_workspace": "切换项目",
        "command_no_folder": "不选择文件夹",
        "command_diff_review": "查看当前差异",
        "command_toggle_history": "切换回滚历史",
        "command_permissions": "打开权限设置",
        "command_resume_latest": "恢复最近任务",
        "recent_workspaces": "最近项目",
        "agent_plan": "执行计划",
        "agent_plan_waiting": "等待计划生成",
        "suggest_run_tests": "运行项目测试",
        "suggest_scan_todo": "查找 TODO",
        "suggest_read_entry": "阅读入口文件",
        "suggest_run_tests_text": "请根据当前项目结构选择合适的测试命令并运行，失败时定位原因。",
        "suggest_scan_todo_text": "请扫描当前项目里的 TODO/FIXME/临时实现，并按优先级列出建议处理项。",
        "suggest_read_entry_text": "请阅读当前项目入口文件和核心配置，说明启动流程和主要模块。",
        "no_recent_workspaces": "暂无最近项目",
        "input_hint": "用自然语言描述任务，Agent 会自己决定是否读取文件、修改代码和执行命令",
        "slash_hint": "输入 / 唤醒命令",
        "slash_commands": "命令",
        "slash_no_matches": "没有匹配的命令",
        "slash_self_improve": "自优化建议",
        "slash_self_improve_desc": "扫描项目并提出代码能力优化建议",
        "slash_self_improve_prompt": "请调用 suggest_self_improvements，列出 5 个当前项目最值得做的代码能力优化建议。",
        "slash_model": "切换模型",
        "slash_model_desc": "切换当前聊天使用的模型",
        "model_switched": "已切换模型：{model}",
        "slash_reasoning": "推理强度",
        "slash_reasoning_desc": "切换当前聊天使用的推理强度",
        "reasoning_switched": "已切换推理强度：{effort}",
        "reasoning_low": "低",
        "reasoning_medium": "中",
        "reasoning_high": "高",
        "reasoning_xhigh": "超高",
        "slash_check_project": "检查项目",
        "slash_fix_tests": "修复测试",
        "slash_explain_project": "解释项目",
        "send": "发送",
        "stop": "停止",
        "stopping": "停止中",
        "messages": "条消息",
        "ready": "就绪",
        "working": "工作中",
        "stopping_status": "停止中",
        "stopped": "已停止",
        "rollback_select": "选择一个回滚记录",
        "rollback_meta_empty": "该版本的文件差异会显示在这里。",
        "rollback_preview_empty": "回滚预览会显示在这里。",
        "no_active_session": "没有活动会话",
        "no_rollback_history": "暂无回滚历史",
        "entries": "条记录",
        "just_now": "刚刚",
        "you": "你",
        "thinking": "正在思考…",
        "preparing_reply": "准备回复…",
        "truncated": "已截断",
        "error_prefix": "错误",
        "search_prefix": "搜索",
        "run_timeline": "运行时间线",
        "run_summary": "运行摘要",
        "self_check": "自检结果",
        "current_diff_review": "当前差异审查",
        "status": "状态",
        "summary": "摘要",
        "files": "文件",
        "missing_paths": "缺失路径",
        "available": "可用",
        "empty": "空",
        "no_active_rollbackable_changes": "当前会话没有可回滚的活跃变更。",
        "resume_task": "恢复任务",
        "resume_history_title": "恢复运行历史",
        "resume_selected": "恢复选中运行",
        "resume_preview": "恢复预览",
        "resume_related_diff": "相关差异",
        "resume_prompt_editor": "恢复提示（可编辑）",
        "copy_resume_prompt": "复制提示",
        "no_resume_history": "暂无需要恢复的运行记录。",
        "resume_prompt_intro": "根据下面的恢复上下文继续上一次 Agent 任务。",
        "resume_prompt_no_restart": "除非上下文明显不可用，否则不要从头开始。",
        "resume_prompt_verify_first": "先核对当前工作区状态，然后继续最高优先级的下一步。",
        "busy_action_message": "当前任务还在执行，请先等待完成。",
        "no_run_log_path": "当前运行还没有可用日志路径。",
        "read_run_log_failed": "读取运行日志失败：{error}",
        "run_debug_title": "Agent 运行调试",
        "run_log_label": "运行日志：{name}",
        "run_review": "运行复盘",
        "quality_gate": "质量门禁",
        "bug_report": "缺陷报告",
        "regression_plan": "回归计划",
        "build_resume_context_failed": "生成恢复上下文失败：{error}",
        "diff_review_failed": "差异审查失败：{error}",
        "agent_run_log": "Agent 执行日志",
        "waiting_tool_call": "等待工具调用",
        "log_summary": "日志摘要",
        "timeline": "时间线",
        "agent_analyzing_tools": "Agent 正在分析任务，工具调用会显示在这里。",
        "waiting_run_log": "等待运行日志",
        "validated_yes": "是",
        "validated_no": "否",
        "tool_detail_expand": "展开工具详情",
        "tool_detail_collapse": "收起工具详情",
        "waiting_tool_output": "等待工具输出...",
        "approval_required": "需要你的确认后继续执行",
        "approval_required_detail": "需要确认：{label}。{reason}",
        "approval_required_label_only": "需要确认：{label}。",
        "allow": "允许",
        "reject": "拒绝",
        "approved_continuing": "已允许，继续执行中…",
        "rejected_returning": "已拒绝，正在返回结果…",
        "quick_actions": "快捷操作",
        "execute": "执行",
        "round_label": "第 {round} 轮",
        "tool_status_preview": "预览",
        "tool_status_running": "执行中",
        "tool_status_success": "成功",
        "tool_status_failed": "失败",
        "tool_previewing": "{name} 预览中",
        "tool_running": "{name} 执行中",
        "tool_done": "{name} 已完成",
        "tool_failed": "{name} 执行失败",
        "tool_field_round": "轮次",
        "tool_field_status": "状态",
        "tool_field_risk": "风险",
        "tool_field_why": "原因",
        "tool_field_preview": "预览",
        "tool_field_input": "输入",
        "tool_field_result": "结果",
        "tool_action_diff": "差异 #{rollback_id}",
        "tool_action_restore": "恢复 #{rollback_id}",
        "tool_action_restore_this": "恢复这个版本",
        "tool_action_undo_rollback": "撤销这次回滚",
        "tool_prompt_preview_rollback_change": "请直接调用 preview_rollback_change 工具，参数 rollback_id={rollback_id}，只展示差异预览，不要执行回滚。",
        "tool_prompt_rollback_change": "请直接调用 rollback_change 工具，参数 rollback_id={rollback_id}，恢复到这个版本，然后给我结果。",
        "tool_prompt_undo_rollback": "请直接调用 rollback_change 工具，参数 rollback_id={rollback_id}，撤销刚才那次回滚，然后给我结果。",
        "rollback_status_meta": "状态：{status} | 文件：{files} | 创建时间：{created}",
        "unknown_path": "未知路径",
        "no_file_details": "没有可用的文件详情",
        "rollback_title": "回滚 #{rollback_id}",
        "rollback_preview_prompt": "请调用 preview_rollback_change 工具，参数 rollback_id={rollback_id}。只展示差异预览，不要执行任何回滚。",
        "rollback_restore_prompt": "请调用 rollback_change 工具，参数 rollback_id={rollback_id}。恢复到这个版本，然后告诉我结果。",
        "empty_subtitle": "像正式产品一样的聊天界面，支持流式回复、Markdown 渲染和 Agent 工具。",
        "feature_streaming": "流式回复",
        "feature_multi_turn": "多轮对话",
        "feature_agent_tools": "Agent 工具",
        "input_shortcut_hint": "Enter 发送 · Shift+Enter 换行 · / 命令",
        "new_session": "新会话",
        "delete_session_title": "删除会话",
        "delete_session_confirm": "确定删除「{title}」吗？",
        "busy_delete_session": "当前任务正在执行中，暂时不能删除会话。",
        "trust_attention": "需要注意",
        "trust_risky": "有风险",
        "trustworthy": "可信",
        "waiting_confirmation": "等待确认",
        "analyzing": "分析中",
        "done": "完成",
        "failed": "失败",
        "call_failed": "调用失败：\n\n{error}",
        "change_update": "文本更新",
        "change_restore_file": "恢复文件",
        "change_delete_file": "删除文件",
        "change_restore_directory": "恢复文件夹",
        "change_delete_directory": "删除文件夹",
        "change_replace_binary": "替换二进制文件",
        "change_replace_item": "替换项目",
        "local_coding_workspace": "本地代码工作区",
        "more": "更多",
        "settings_dev": "设置（开发中）",
        "feature_in_development": "这个功能还在开发中。",
        "sidebar_shortcuts": "Ctrl+N 当前项目新建 · Delete 删除",
        "scroll_bottom": "回到底部",
        "agent_mode_tip": "切换为代码 Agent：可读文件、改文件、运行命令",
        "rollback_history_title": "回滚历史",
    },
    "en": {
        "settings": "Permissions",
        "settings_title": "Settings",
        "settings_heading": "App Settings",
        "language": "Language",
        "language_zh": "Chinese",
        "language_en": "English",
        "read_scope": "Read scope",
        "write_scope": "Write scope",
        "command_scope": "Command scope",
        "extra_write_roots": "Extra write roots",
        "extra_command_roots": "Extra command roots",
        "settings_hint": "workspace limits access to WORKSPACE_ROOT plus extra roots; all allows the whole filesystem.",
        "browse": "Browse",
        "save": "Save",
        "cancel": "Cancel",
        "select_allowed_directory": "Select allowed directory",
        "path_placeholder": "Separate multiple paths with ; on Windows",
        "settings_busy": "Wait for the current agent task to finish before changing settings.",
        "settings_saved": "Settings updated.",
        "permissions": "Permissions",
        "permissions_saved": "Permissions updated.",
        "read_permission": "Read",
        "write_permission": "Write",
        "command_permission": "Command",
        "workspace_scope": "Workspace",
        "all_scope": "All",
        "refresh": "Refresh",
        "open_in_chat": "Open In Chat",
        "restore": "Restore",
        "history": "History",
        "diff_review": "Diff",
        "resume_history": "Resume",
        "diff_review_tip": "Review the current session's rollbackable change summary before trusting code edits.",
        "resume_history_tip": "Pick a previous run that needs follow-up, edit the resume prompt, then continue it.",
        "rollback_history_tip": "Inspect individual rollback records, preview version diffs, or restore a selected version.",
        "activity": "Activity",
        "activity_title": "Activity Panel",
        "activity_tip": "Open current diffs, resumable runs, and rollback history from one place.",
        "activity_intro": "Review, resume, and rollback actions live together here so the header does not duplicate recovery entry points.",
        "activity_back": "Back",
        "activity_back_to_activity": "Back to Activity",
        "activity_open_diff": "Review current diff",
        "activity_open_resume": "Resume previous run",
        "activity_open_history": "Open rollback history",
        "activity_open_analytics": "View run analytics",
        "activity_status_unavailable": "Status unavailable",
        "activity_diff_clean": "No rollbackable changes",
        "activity_diff_count": "{count} changed path(s)",
        "activity_diff_recent_empty": "No changed paths to show.",
        "activity_more_items": "+{count} more",
        "activity_resume_clean": "No runs need resume",
        "activity_resume_count": "{count} run(s) need attention",
        "activity_resume_recent_empty": "No recent runs need resume.",
        "activity_rollback_clean": "No rollback history",
        "activity_rollback_count": "{count} rollback record(s)",
        "activity_analytics_empty": "No runs to analyze",
        "activity_analytics_summary": "{runs} run(s), {problems} need attention",
        "run_analytics_tip": "Summarize quality gates, validation failures, unverified changes, failed tools, and model error trends across recent runs.",
        "run_analytics_title": "Run Analytics",
        "workspace": "Workspace",
        "switch_workspace": "Switch workspace",
        "select_workspace": "Select workspace",
        "workspace_changed": "Current chat workspace updated.",
        "workspace_missing": "Workspace does not exist: {path}",
        "workspace_label": "Workspace: {path}",
        "workspace_button_label": "Project: {name}",
        "workspace_button_tooltip": "Click to switch the target project for this chat: {path}",
        "new_chat": "+  New chat",
        "new_chat_for_folder": "+  New project chat",
        "select_workspace_for_new_chat": "Select workspace for new chat",
        "clear_workspace": "No folder",
        "no_project": "No project selected",
        "no_project_label": "Project: none",
        "no_project_tooltip": "This chat is not bound to a project and will use normal chat.",
        "no_project_for_workspace_action": "This chat has no project. Select a project first.",
        "no_project_chat_mode": "Normal chat",
        "no_project_chat_detail": "No file access",
        "project_chat_mode": "Project chat",
        "session_current_marker": "Current",
        "session_created_at": "Created {time}",
        "prompt_check_project": "Check project",
        "prompt_fix_tests": "Fix tests",
        "prompt_explain_project": "Explain project",
        "prompt_check_project_text": "Inspect the current project structure and summarize the main modules, entry points, test entry, and suggested next steps.",
        "prompt_fix_tests_text": "Run the project tests, diagnose any failures, fix them, and report the changes and verification result.",
        "prompt_explain_project_text": "Explain this project's purpose, code structure, run workflow, and main risks.",
        "command_palette": "Command Palette",
        "command_palette_placeholder": "Type a command, e.g. switch project / new chat / diff",
        "command_new_chat": "New chat",
        "command_new_project_chat": "New project chat",
        "command_switch_workspace": "Switch project",
        "command_no_folder": "No folder",
        "command_diff_review": "Show current diff",
        "command_toggle_history": "Toggle rollback history",
        "command_permissions": "Open permissions",
        "command_resume_latest": "Resume latest task",
        "recent_workspaces": "Recent projects",
        "agent_plan": "Plan",
        "agent_plan_waiting": "Waiting for plan",
        "suggest_run_tests": "Run tests",
        "suggest_scan_todo": "Find TODOs",
        "suggest_read_entry": "Read entry files",
        "suggest_run_tests_text": "Choose and run the right test command for this project. If it fails, diagnose the cause.",
        "suggest_scan_todo_text": "Scan this project for TODO/FIXME/temporary implementations and list the highest-priority follow-ups.",
        "suggest_read_entry_text": "Read the project entry files and core config, then explain the startup flow and main modules.",
        "no_recent_workspaces": "No recent projects",
        "input_hint": "Describe a task. Agent can read files, edit code, and run commands when needed.",
        "slash_hint": "Type / for commands",
        "slash_commands": "Commands",
        "slash_no_matches": "No matching commands",
        "slash_self_improve": "Self-improve suggestions",
        "slash_self_improve_desc": "Scan the project and suggest coding-capability improvements",
        "slash_self_improve_prompt": "Call suggest_self_improvements and list the 5 most valuable coding-capability improvements for this project.",
        "slash_model": "Switch model",
        "slash_model_desc": "Switch the model used by this chat",
        "model_switched": "Model switched: {model}",
        "slash_reasoning": "Reasoning effort",
        "slash_reasoning_desc": "Switch the reasoning effort used by this chat",
        "reasoning_switched": "Reasoning effort switched: {effort}",
        "reasoning_low": "Low",
        "reasoning_medium": "Medium",
        "reasoning_high": "High",
        "reasoning_xhigh": "Extra high",
        "slash_check_project": "Check project",
        "slash_fix_tests": "Fix tests",
        "slash_explain_project": "Explain project",
        "send": "Send",
        "stop": "Stop",
        "stopping": "Stopping",
        "messages": "messages",
        "ready": "Ready",
        "working": "Working",
        "stopping_status": "Stopping",
        "stopped": "Stopped",
        "rollback_select": "Select a rollback entry",
        "rollback_meta_empty": "The exact file diff for that version will appear here.",
        "rollback_preview_empty": "Rollback preview will appear here.",
        "no_active_session": "No active session",
        "no_rollback_history": "No rollback history yet",
        "entries": "entries",
        "just_now": "Just now",
        "you": "You",
        "thinking": "Thinking...",
        "preparing_reply": "Preparing reply...",
        "truncated": "truncated",
        "error_prefix": "Error",
        "search_prefix": "Search",
        "run_timeline": "Run Timeline",
        "run_summary": "Run Summary",
        "self_check": "Self Check",
        "current_diff_review": "Current Diff Review",
        "status": "Status",
        "summary": "Summary",
        "files": "Files",
        "missing_paths": "Missing paths",
        "available": "available",
        "empty": "empty",
        "no_active_rollbackable_changes": "No active rollbackable changes in this session.",
        "resume_task": "Resume Task",
        "resume_history_title": "Resume Run History",
        "resume_selected": "Resume selected run",
        "resume_preview": "Resume Preview",
        "resume_related_diff": "Related Diff",
        "resume_prompt_editor": "Resume prompt (editable)",
        "copy_resume_prompt": "Copy prompt",
        "no_resume_history": "No runs need resume.",
        "resume_prompt_intro": "Continue the previous Agent task using this resume context.",
        "resume_prompt_no_restart": "Do not restart from scratch unless the context is clearly unusable.",
        "resume_prompt_verify_first": "First verify the current workspace state, then continue with the highest-priority next step.",
        "busy_action_message": "Current task is still running. Wait for it to finish first.",
        "no_run_log_path": "The current run has no available log path yet.",
        "read_run_log_failed": "Read run log failed: {error}",
        "run_debug_title": "Agent Run Debug",
        "run_log_label": "Run log: {name}",
        "run_review": "Run Review",
        "quality_gate": "Quality Gate",
        "bug_report": "Bug Report",
        "regression_plan": "Regression Plan",
        "build_resume_context_failed": "Build resume context failed: {error}",
        "diff_review_failed": "Diff review failed: {error}",
        "agent_run_log": "Agent Run Log",
        "waiting_tool_call": "Waiting for tool calls",
        "log_summary": "Log Summary",
        "timeline": "Timeline",
        "agent_analyzing_tools": "Agent is analyzing the task. Tool calls will appear here.",
        "waiting_run_log": "Waiting for run log",
        "validated_yes": "yes",
        "validated_no": "no",
        "tool_detail_expand": "Expand tool details",
        "tool_detail_collapse": "Collapse tool details",
        "waiting_tool_output": "Waiting for tool output...",
        "approval_required": "Approval required before continuing",
        "approval_required_detail": "Approval required: {label}. {reason}",
        "approval_required_label_only": "Approval required: {label}.",
        "allow": "Allow",
        "reject": "Reject",
        "approved_continuing": "Approved. Continuing...",
        "rejected_returning": "Rejected. Returning result...",
        "quick_actions": "Quick Actions",
        "execute": "Run",
        "round_label": "Round {round}",
        "tool_status_preview": "Preview",
        "tool_status_running": "Running",
        "tool_status_success": "Success",
        "tool_status_failed": "Failed",
        "tool_previewing": "{name} previewing",
        "tool_running": "{name} running",
        "tool_done": "{name} completed",
        "tool_failed": "{name} failed",
        "tool_field_round": "Round",
        "tool_field_status": "Status",
        "tool_field_risk": "Risk",
        "tool_field_why": "Why",
        "tool_field_preview": "Preview",
        "tool_field_input": "Input",
        "tool_field_result": "Result",
        "tool_action_diff": "Diff #{rollback_id}",
        "tool_action_restore": "Restore #{rollback_id}",
        "tool_action_restore_this": "Restore this version",
        "tool_action_undo_rollback": "Undo this rollback",
        "tool_prompt_preview_rollback_change": "Call the preview_rollback_change tool with rollback_id={rollback_id}. Show the diff preview only and do not perform any rollback.",
        "tool_prompt_rollback_change": "Call the rollback_change tool with rollback_id={rollback_id}. Restore that version and then tell me the result.",
        "tool_prompt_undo_rollback": "Call the rollback_change tool with rollback_id={rollback_id}. Undo the previous rollback and then tell me the result.",
        "rollback_status_meta": "Status: {status} | Files: {files} | Created: {created}",
        "unknown_path": "unknown path",
        "no_file_details": "No file details available",
        "rollback_title": "Rollback #{rollback_id}",
        "rollback_preview_prompt": "Call the preview_rollback_change tool with rollback_id={rollback_id}. Show the diff preview only and do not perform any rollback.",
        "rollback_restore_prompt": "Call the rollback_change tool with rollback_id={rollback_id}. Restore that version and then tell me the result.",
        "empty_subtitle": "A polished chat interface with streaming replies, Markdown rendering, and Agent tools.",
        "feature_streaming": "Streaming replies",
        "feature_multi_turn": "Multi-turn chat",
        "feature_agent_tools": "Agent tools",
        "input_shortcut_hint": "Enter to send · Shift+Enter for newline · / commands",
        "new_session": "New chat",
        "delete_session_title": "Delete Chat",
        "delete_session_confirm": "Delete \"{title}\"?",
        "busy_delete_session": "Current task is still running, so the chat cannot be deleted yet.",
        "trust_attention": "Needs attention",
        "trust_risky": "Risky",
        "trustworthy": "Trusted",
        "waiting_confirmation": "Waiting for approval",
        "analyzing": "Analyzing",
        "done": "Done",
        "failed": "Failed",
        "call_failed": "Call failed:\n\n{error}",
        "change_update": "Text update",
        "change_restore_file": "Restore file",
        "change_delete_file": "Delete file",
        "change_restore_directory": "Restore folder",
        "change_delete_directory": "Delete folder",
        "change_replace_binary": "Replace binary",
        "change_replace_item": "Replace item",
        "local_coding_workspace": "Local coding workspace",
        "more": "More",
        "settings_dev": "Settings (in development)",
        "feature_in_development": "This feature is still in development.",
        "sidebar_shortcuts": "Ctrl+N Current project · Delete Remove",
        "scroll_bottom": "Scroll to bottom",
        "agent_mode_tip": "Switch to coding Agent: read files, edit files, and run commands",
        "rollback_history_title": "Rollback History",
    },
}


def _language_code(value: str | None = None) -> str:
    raw = str(value if value is not None else getattr(app_config, "APP_LANGUAGE", "zh")).strip().lower()
    return "en" if raw == "en" else "zh"


def _t(key: str) -> str:
    lang = _language_code()
    return UI_TEXT.get(lang, UI_TEXT["zh"]).get(key, UI_TEXT["zh"].get(key, key))


def _tf(key: str, **kwargs: Any) -> str:
    return _t(key).format(**kwargs)


def _reasoning_effort_label(effort: str) -> str:
    key = {
        "low": "reasoning_low",
        "medium": "reasoning_medium",
        "high": "reasoning_high",
        "xhigh": "reasoning_xhigh",
    }.get(normalize_reasoning_effort(effort))
    return _t(key) if key else effort


def _slash_commands() -> list[dict[str, str]]:
    return [
        {
            "name": "/self",
            "label": _t("slash_self_improve"),
            "description": _t("slash_self_improve_desc"),
            "prompt": _t("slash_self_improve_prompt"),
        },
        {
            "name": "/check",
            "label": _t("slash_check_project"),
            "description": _t("prompt_check_project_text"),
            "prompt": _t("prompt_check_project_text"),
        },
        {
            "name": "/test",
            "label": _t("slash_fix_tests"),
            "description": _t("prompt_fix_tests_text"),
            "prompt": _t("prompt_fix_tests_text"),
        },
        {
            "name": "/explain",
            "label": _t("slash_explain_project"),
            "description": _t("prompt_explain_project_text"),
            "prompt": _t("prompt_explain_project_text"),
        },
        {
            "name": "/model",
            "label": _t("slash_model"),
            "description": _t("slash_model_desc"),
            "prompt": "",
            "action": "open_model_menu",
        },
        {
            "name": "/reasoning",
            "label": _t("slash_reasoning"),
            "description": _t("slash_reasoning_desc"),
            "prompt": "",
            "action": "open_reasoning_menu",
        },
    ]


def _slash_model_commands() -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    for model in available_models():
        display = model_display_name(model)
        commands.append(
            {
                "name": f"/model {display}",
                "label": _t("slash_model"),
                "description": f"{_t('slash_model_desc')}: {display}",
                "prompt": "",
                "action": "set_model",
                "model": model,
            }
        )
    return commands


def _slash_reasoning_commands() -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    for effort in available_reasoning_efforts():
        display = _reasoning_effort_label(effort)
        commands.append(
            {
                "name": f"/reasoning {display}",
                "label": _t("slash_reasoning"),
                "description": f"{_t('slash_reasoning_desc')}: {display}",
                "prompt": "",
                "action": "set_reasoning",
                "reasoning_effort": effort,
            }
        )
    return commands


def _slash_command_matches(text: str, limit: int = 8) -> list[dict[str, str]]:
    original = str(text or "")
    raw = original.strip()
    if not raw.startswith("/"):
        return []
    query = raw[1:].strip().lower()
    source = _slash_commands()
    if query.startswith("model"):
        model_query = query.removeprefix("model").strip()
        source = _slash_model_commands() if model_query or original.rstrip("\n").endswith(" ") else _slash_commands()
        query = model_query if model_query else "model"
    elif query.startswith("reasoning"):
        reasoning_query = query.removeprefix("reasoning").strip()
        source = (
            _slash_reasoning_commands()
            if reasoning_query or original.rstrip("\n").endswith(" ")
            else _slash_commands()
        )
        query = reasoning_query if reasoning_query else "reasoning"
    matches: list[dict[str, str]] = []
    for command in source:
        haystack = " ".join(
            [
                command.get("name", ""),
                command.get("label", ""),
                command.get("description", ""),
            ]
        ).lower()
        if not query or query in haystack:
            matches.append(command)
        if len(matches) >= max(1, int(limit)):
            break
    return matches


MESSAGE_BODY_STYLE = (
    highlight_css()
    + """
body {
    margin: 0;
    padding: 0;
    background: transparent;
    color: __TEXT_MAIN__;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 14px;
}
p {
    margin: 0 0 10px;
}
p:last-child {
    margin-bottom: 0;
}
ul, ol {
    margin: 6px 0 8px 22px;
    padding: 0;
}
li {
    margin-bottom: 4px;
}
h1, h2, h3, h4 {
    margin: 14px 0 8px;
    color: #F8FAFC;
    line-height: 1.2;
}
h1 {
    font-size: 20px;
}
h2 {
    font-size: 17px;
}
h3 {
    font-size: 15px;
}
blockquote {
    margin: 8px 0;
    padding: 0 0 0 12px;
    color: __TEXT_SUB__;
    border-left: 3px solid __ACCENT__;
}
a {
    color: #93C5FD;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
table {
    border-collapse: collapse;
    margin: 8px 0;
    width: 100%;
}
th, td {
    border: 1px solid __BORDER__;
    padding: 6px 10px;
    font-size: 13px;
}
th {
    background: rgba(148, 163, 184, 0.08);
}
pre {
    background: #0B1120;
    border: 1px solid __BORDER__;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0;
    white-space: pre-wrap;
}
code {
    font-family: Consolas, "Cascadia Mono", "SFMono-Regular", monospace;
    font-size: 12.5px;
    background: rgba(124, 58, 237, 0.14);
    color: #E9D5FF;
    padding: 2px 6px;
    border-radius: 6px;
}
pre code {
    background: transparent;
    color: inherit;
    padding: 0;
}
img {
    max-width: 100%;
}
.cursor {
    color: __ACCENT2__;
    font-weight: 700;
}
.typing {
    color: __TEXT_SUB__;
    font-style: italic;
}
.error-box {
    color: #FCA5A5;
    background: rgba(127, 29, 29, 0.22);
    border: 1px solid rgba(248, 113, 113, 0.34);
    border-left: 3px solid __ERROR__;
    border-radius: 12px;
    padding: 10px 12px;
}
"""
    .replace("__TEXT_MAIN__", C_TEXT_MAIN)
    .replace("__TEXT_SUB__", C_TEXT_SUB)
    .replace("__ACCENT__", C_ACCENT)
    .replace("__ACCENT2__", C_ACCENT_2)
    .replace("__BORDER__", C_BORDER)
    .replace("__ERROR__", C_ERROR)
)


def _format_message_time(created_at: str | None) -> str:
    if not created_at:
        return _t("just_now")
    raw = str(created_at).strip().replace("T", " ")
    try:
        return datetime.fromisoformat(raw).strftime("%H:%M")
    except Exception:
        return raw


def _format_short_datetime(value: str | None) -> str:
    if not value:
        return _t("just_now")
    raw = str(value).strip().replace("T", " ")
    try:
        return datetime.fromisoformat(raw).strftime("%m-%d %H:%M")
    except Exception:
        return raw[:16] if len(raw) > 16 else raw


def _chip_label(text: str, fg: str, bg: str, border: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    label.setStyleSheet(
        f"background: {bg}; color: {fg}; border: 1px solid {border}; "
        "border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 700;"
    )
    return label


def _button_style(kind: str = "secondary", *, radius: int = 12, compact: bool = False) -> str:
    padding = "6px 10px" if compact else "7px 12px"
    size = "11px" if compact else "12px"
    weight = "700"
    if kind == "primary":
        return (
            "QPushButton {"
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2});"
            "color: #03111A;"
            "border: none;"
            f"border-radius: {radius}px;"
            f"padding: {padding};"
            f"font-size: {size};"
            f"font-weight: {weight};"
            "}"
            "QPushButton:disabled { background: rgba(148, 163, 184, 0.14); color: #64748B; }"
        )
    if kind == "pill":
        return (
            "QPushButton {"
            "background: rgba(255, 255, 255, 0.018);"
            "color: #8EA0B5;"
            f"border: 1px solid {C_BORDER_SOFT};"
            "border-radius: 999px;"
            f"padding: {padding};"
            f"font-size: {size};"
            f"font-weight: {weight};"
            "}"
            "QPushButton:hover { background: rgba(56, 189, 248, 0.08); color: #BAE6FD; }"
        )
    if kind == "danger":
        return (
            "QPushButton {"
            "background: rgba(239, 68, 68, 0.14); color: #FCA5A5;"
            "border: 1px solid rgba(248, 113, 113, 0.28);"
            f"border-radius: {radius}px;"
            f"padding: {padding};"
            f"font-size: {size};"
            f"font-weight: {weight};"
            "}"
            "QPushButton:disabled { background: rgba(148, 163, 184, 0.10); color: #64748B; }"
        )
    return (
        "QPushButton {"
        "background: rgba(255, 255, 255, 0.026);"
        "color: #CBD5E1;"
        f"border: 1px solid {C_BORDER};"
        f"border-radius: {radius}px;"
        f"padding: {padding};"
        f"font-size: {size};"
        f"font-weight: {weight};"
        "}"
        "QPushButton:hover { background: rgba(56, 189, 248, 0.08); border-color: rgba(56, 189, 248, 0.28); }"
    )


def _dialog_style() -> str:
    return (
        f"QDialog {{ background: {C_BG_PANEL}; color: {C_TEXT_MAIN}; }}"
        f"QLabel {{ color: {C_TEXT_SUB}; }}"
        "QDialogButtonBox QPushButton {"
        "background: rgba(255, 255, 255, 0.026);"
        "color: #CBD5E1;"
        f"border: 1px solid {C_BORDER};"
        "border-radius: 10px;"
        "padding: 6px 12px;"
        "font-size: 11px;"
        "font-weight: 700;"
        "}"
        "QDialogButtonBox QPushButton:hover { background: rgba(56, 189, 248, 0.08); }"
    )


def _text_view_style() -> str:
    return (
        f"background: {C_BG_SURFACE}; color: {C_TEXT_MAIN}; "
        f"border: 1px solid {C_BORDER}; border-radius: 14px; padding: 10px;"
    )


def _menu_style() -> str:
    return (
        f"background: {C_BG_PANEL}; color: {C_TEXT_MAIN}; border: 1px solid {C_BORDER};"
        "QMenu::item { padding: 7px 26px 7px 12px; }"
        "QMenu::item:selected { background: rgba(56, 189, 248, 0.14); }"
    )


def _avatar_label(text: str, bg: str, size: int = 34) -> QLabel:
    label = QLabel(text.upper())
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background: {bg}; color: #fff; border-radius: {size // 2}px; "
        "font-size: 12px; font-weight: 700;"
    )
    return label


def _clear_layout(layout: QVBoxLayout | QHBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)


def _body_width_for_card(viewport_width: int, role: str, text: str) -> int:
    max_width = max(360, min(760, int(viewport_width * 0.72))) if viewport_width > 0 else 700
    if role != "user":
        return max_width

    metrics = QFontMetrics(QFont("Microsoft YaHei", 14))
    lines = text.splitlines() or [text]
    longest = max((metrics.horizontalAdvance(line) for line in lines), default=0)
    estimated = longest + 92
    return max(220, min(max_width, estimated))


def _pretty_json(value: Any, limit: int = 2600) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if len(text) > limit:
        return text[:limit] + f"\n... ({_t('truncated')})"
    return text


def _looks_like_diff_preview(text: str) -> bool:
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return False
    diff_markers = ("diff --git ", "--- ", "+++ ", "@@ ")
    if any(line.startswith(diff_markers) for line in lines[:8]):
        return True
    plus_minus = sum(
        1
        for line in lines[:40]
        if line.startswith("+") or line.startswith("-")
    )
    return plus_minus >= 4


def _preview_markdown_block(preview: str) -> str:
    fence = "diff" if _looks_like_diff_preview(preview) else "text"
    return f"```{fence}\n{preview}\n```"


def _tool_policy_label(policy: dict[str, Any] | None) -> str:
    if not isinstance(policy, dict):
        return ""
    label = str(policy.get("risk_label") or "").strip()
    if label:
        return label
    level = str(policy.get("risk_level") or "").strip()
    return level.title() if level else ""


def _tool_policy_reason(policy: dict[str, Any] | None) -> str:
    if not isinstance(policy, dict):
        return ""
    return str(policy.get("reason") or "").strip()


def _rollback_change_type_label(action: str) -> str:
    mapping = {
        "update": _t("change_update"),
        "restore_file": _t("change_restore_file"),
        "delete_file": _t("change_delete_file"),
        "restore_directory": _t("change_restore_directory"),
        "delete_directory": _t("change_delete_directory"),
        "replace_binary": _t("change_replace_binary"),
        "replace_item": _t("change_replace_item"),
    }
    return mapping.get(str(action or "").strip(), str(action or "Change"))


def _run_timeline_markdown(run_log_path: str, *, limit: int = 80) -> str:
    timeline = run_log_timeline(run_log_path)
    lines = [f"### {_t('run_timeline')}", ""]
    for item in timeline[:limit]:
        title = str(item.get("title") or item.get("event") or "event")
        timestamp = str(item.get("timestamp") or "")
        detail = str(item.get("detail") or "").strip()
        line = f"- `{timestamp}` {title}" if timestamp else f"- {title}"
        if detail:
            line += f" - {detail}"
        lines.append(line)
    if len(timeline) > limit:
        lines.append(f"- ... {len(timeline) - limit} more event(s)")
    return "\n".join(lines)


def _run_debug_markdown(run_log_path: str, mode: str) -> str:
    if mode == "timeline":
        return _run_timeline_markdown(run_log_path)
    if mode in {"review", "quality_gate", "bug_report", "regression_plan"}:
        review = build_run_review(run_log_path)
        if mode == "review":
            return format_run_review_markdown(review)
        if mode == "quality_gate":
            return format_quality_gate_markdown(review)
        if mode == "bug_report":
            return format_bug_report_markdown(review)
        return format_regression_plan_markdown(review)
    return "\n\n".join(
        [
            f"### {_t('run_summary')}",
            f"```text\n{summarize_run_for_display(run_log_path)}\n```",
            f"### {_t('self_check')}",
            f"```text\n{format_run_health_report(run_log_path)}\n```",
        ]
    )


def _diff_review_markdown(preview: dict[str, Any]) -> str:
    paths = preview.get("paths") if isinstance(preview.get("paths"), list) else []
    missing_paths = preview.get("missing_paths") if isinstance(preview.get("missing_paths"), list) else []
    available = bool(preview.get("available", False))
    preview_text = str(preview.get("preview") or "").strip()
    summary = str(preview.get("summary") or "").strip()

    lines = [f"### {_t('current_diff_review')}", ""]
    lines.append(f"**{_t('status')}**: {_t('available') if available else _t('empty')}")
    lines.append("")
    if summary:
        lines.append(f"**{_t('summary')}**: {summary}")
        lines.append("")
    lines.append(f"**{_t('files')}**: {len(paths)}")
    lines.append("")
    if paths:
        for path in paths:
            lines.append(f"- `{path}`")
    else:
        lines.append(f"- {_t('no_active_rollbackable_changes')}")
    if missing_paths:
        lines.append("")
        lines.append(f"**{_t('missing_paths')}**")
        lines.append("")
        for path in missing_paths:
            lines.append(f"- `{path}`")
    symbol_lines = _symbol_impacts_markdown_lines(preview.get("symbol_impacts"))
    if symbol_lines:
        lines.append("")
        lines.append("**Symbol impacts**")
        lines.append("")
        lines.extend(symbol_lines)
    if preview_text:
        lines.extend(["", _preview_markdown_block(preview_text)])
    return "\n".join(lines)


def _symbol_impacts_markdown_lines(raw_impacts: Any) -> list[str]:
    impacts = raw_impacts if isinstance(raw_impacts, list) else []
    lines: list[str] = []
    for impact in impacts[:6]:
        if not isinstance(impact, dict):
            continue
        symbol = str(impact.get("symbol") or "").strip()
        if not symbol:
            continue
        definition = str(impact.get("definition_path") or "unknown")
        refs = impact.get("reference_count")
        tests = impact.get("related_tests") if isinstance(impact.get("related_tests"), list) else []
        line = f"- `{symbol}` -> `{definition}`"
        if refs is not None:
            line += f" | refs: {refs}"
        if tests:
            line += " | tests: " + ", ".join(f"`{test}`" for test in tests[:3])
        lines.append(line)
    return lines


def _symbol_impacts_inline(raw_impacts: Any) -> str:
    impacts = raw_impacts if isinstance(raw_impacts, list) else []
    symbols = [
        str(impact.get("symbol"))
        for impact in impacts[:3]
        if isinstance(impact, dict) and impact.get("symbol")
    ]
    return ", ".join(symbols)


def _resume_task_prompt(context: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            _t("resume_prompt_intro"),
            _t("resume_prompt_no_restart"),
            _t("resume_prompt_verify_first"),
            "```text",
            format_resume_context(context),
            "```",
        ]
    )


def _resume_history_candidates(
    rows: list[dict[str, Any]],
    *,
    workspace_root: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    workspace = str(workspace_root or "").strip()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if workspace and str(row.get("workspace_root") or "") != workspace:
            continue
        status = str(row.get("status") or "")
        health = str(row.get("health") or "")
        if (
            status != "completed"
            or health in {"fail", "warn"}
            or str(row.get("quality_gate_status") or "") in {"fail", "warn"}
            or bool(row.get("validation_failed"))
            or bool(row.get("unverified"))
            or int(row.get("failed_tool_count") or 0) > 0
        ):
            candidates.append(row)
        if len(candidates) >= limit:
            break
    return candidates


def _resume_history_item_label(row: dict[str, Any]) -> str:
    started = str(row.get("started_at") or "unknown")
    run_id = str(row.get("run_id") or "unknown")
    status = str(row.get("status") or "running")
    health = str(row.get("health") or "unknown")
    priority_bits: list[str] = []
    if row.get("validation_failed"):
        priority_bits.append("validation_failed")
    if row.get("unverified"):
        priority_bits.append("unverified")
    gate_status = str(row.get("quality_gate_status") or "").strip()
    if gate_status in {"fail", "warn"}:
        priority_bits.append(f"gate:{gate_status}")
    failed_count = int(row.get("failed_tool_count") or 0)
    if failed_count:
        priority_bits.append(f"failed_tools:{failed_count}")
    if status != "completed":
        priority_bits.append(status)
    detail = ", ".join(priority_bits) if priority_bits else health
    return f"{started} | {status}/{health} | {detail} | {run_id[:10]}"


def _resume_history_markdown(
    context: dict[str, Any], diff_preview: dict[str, Any] | None = None
) -> str:
    sections = [
        f"### {_t('resume_preview')}",
        f"```text\n{format_resume_context(context)}\n```",
    ]
    if isinstance(diff_preview, dict):
        sections.extend(
            [
                f"### {_t('resume_related_diff')}",
                _diff_review_markdown(diff_preview),
            ]
        )
    return "\n\n".join(sections)


def _activity_status_summary(
    kind: str,
    *,
    count: int | None = None,
    unavailable: bool = False,
) -> str:
    if unavailable or count is None:
        return _t("activity_status_unavailable")
    safe_count = max(0, int(count))
    if kind == "diff":
        return _tf("activity_diff_count", count=safe_count) if safe_count else _t("activity_diff_clean")
    if kind == "resume":
        return _tf("activity_resume_count", count=safe_count) if safe_count else _t("activity_resume_clean")
    if kind == "rollback":
        return (
            _tf("activity_rollback_count", count=safe_count)
            if safe_count
            else _t("activity_rollback_clean")
        )
    return _t("activity_status_unavailable")


def _activity_recent_resume_lines(rows: list[dict[str, Any]], limit: int = 3) -> list[str]:
    selected = rows[: max(0, int(limit))]
    if not selected:
        return [_t("activity_resume_recent_empty")]
    return [_resume_history_item_label(row) for row in selected]


def _activity_recent_path_lines(paths: list[str], limit: int = 3) -> list[str]:
    clean_paths = [str(path) for path in paths if str(path).strip()]
    if not clean_paths:
        return [_t("activity_diff_recent_empty")]
    safe_limit = max(0, int(limit))
    lines = [f"`{path}`" for path in clean_paths[:safe_limit]]
    remaining = len(clean_paths) - safe_limit
    if remaining > 0:
        lines.append(_tf("activity_more_items", count=remaining))
    return lines


def _activity_analytics_summary(analytics: dict[str, Any] | None) -> str:
    if not isinstance(analytics, dict):
        return _t("activity_status_unavailable")
    run_count = int(analytics.get("run_count") or 0)
    if run_count <= 0:
        return _t("activity_analytics_empty")
    problem_count = len(analytics.get("recent_problem_runs") or [])
    return _tf("activity_analytics_summary", runs=run_count, problems=problem_count)


def _session_title_for_workspace(path: str | Path) -> str:
    root = Path(path)
    return root.name or _t("new_session")


def _session_workspace_summary(session: dict[str, Any], *, current: bool = False) -> str:
    workspace_root = str(session.get("workspace_root") or "").strip()
    created = _tf("session_created_at", time=_format_short_datetime(str(session.get("created_at") or "")))
    marker = f" · {_t('session_current_marker')}" if current else ""
    if not workspace_root:
        return f"{_t('no_project_chat_mode')} · {_t('no_project_chat_detail')}{marker}"
    workspace_name = Path(workspace_root).name or workspace_root
    return f"{workspace_name} · {created}{marker}"


def _recent_workspace_roots(sessions: list[dict[str, Any]], *, limit: int = 6) -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()
    for session in sessions:
        raw = str(session.get("workspace_root") or "").strip()
        if not raw:
            continue
        try:
            root = str(Path(raw).expanduser().resolve())
        except Exception:
            root = raw
        if root in seen or not Path(root).exists():
            continue
        seen.add(root)
        roots.append(root)
        if len(roots) >= limit:
            break
    return roots


def _project_quick_prompts(workspace_root: str) -> list[dict[str, str]]:
    prompts = [
        {"label": _t("suggest_run_tests"), "prompt": _t("suggest_run_tests_text")},
        {"label": _t("suggest_scan_todo"), "prompt": _t("suggest_scan_todo_text")},
        {"label": _t("suggest_read_entry"), "prompt": _t("suggest_read_entry_text")},
    ]
    if not str(workspace_root or "").strip():
        return prompts
    try:
        project_map = build_project_map(Path(workspace_root))
        summary = summarize_project_map(project_map)
    except Exception:
        return prompts

    entry_files = summary.get("entry_files") if isinstance(summary.get("entry_files"), list) else []
    config_files = summary.get("config_files") if isinstance(summary.get("config_files"), list) else []
    if entry_files:
        prompts[2]["prompt"] = (
            f"{_t('suggest_read_entry_text')}\n\n"
            f"优先阅读这些入口文件 / Prioritize these entry files: {', '.join(str(item) for item in entry_files[:5])}"
        )
    elif config_files:
        prompts[2]["prompt"] = (
            f"{_t('suggest_read_entry_text')}\n\n"
            f"优先阅读这些配置文件 / Prioritize these config files: {', '.join(str(item) for item in config_files[:5])}"
        )
    return prompts


def _plan_steps_summary(plan: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for raw in plan[:6]:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "pending")
        title = str(raw.get("title") or raw.get("id") or "step")
        detail = str(raw.get("detail") or "").strip()
        marker = {
            "done": "✓",
            "active": "●",
            "failed": "!",
            "skipped": "–",
        }.get(status, "○")
        line = f"{marker} {title}"
        if detail:
            line += f" · {detail}"
        lines.append(line)
    return lines


def _workspace_button_label(path: str | Path) -> str:
    if str(path).strip() == "":
        return _t("no_project_label")
    root = Path(path)
    name = root.name or str(root)
    return _tf("workspace_button_label", name=name)


def _tool_entry_actions(
    name: str,
    result: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    if not isinstance(result, dict):
        return []

    actions: list[dict[str, str]] = []
    if name == "list_rollback_history":
        entries = result.get("entries") if isinstance(result.get("entries"), list) else []
        for entry in entries[:4]:
            if not isinstance(entry, dict):
                continue
            rollback_id = entry.get("rollback_id")
            if not rollback_id:
                continue
            actions.append(
                {
                    "label": _tf("tool_action_diff", rollback_id=rollback_id),
                    "prompt": (
                        _tf("tool_prompt_preview_rollback_change", rollback_id=int(rollback_id))
                    ),
                }
            )
            if bool(entry.get("available", False)):
                actions.append(
                    {
                        "label": _tf("tool_action_restore", rollback_id=rollback_id),
                        "prompt": (
                            _tf("tool_prompt_rollback_change", rollback_id=int(rollback_id))
                        ),
                    }
                )
        return actions

    if name == "preview_rollback_change":
        rollback_id = result.get("rollback_id")
        if rollback_id and bool(result.get("available", False)):
            actions.append(
                {
                    "label": _t("tool_action_restore_this"),
                    "prompt": (
                        _tf("tool_prompt_rollback_change", rollback_id=int(rollback_id))
                    ),
                }
            )
        return actions

    if name in {"rollback_last_change", "rollback_change"}:
        undo_rollback_id = result.get("undo_rollback_id")
        if undo_rollback_id:
            actions.append(
                {
                    "label": _t("tool_action_undo_rollback"),
                    "prompt": (
                        _tf("tool_prompt_undo_rollback", rollback_id=int(undo_rollback_id))
                    ),
                }
            )
        return actions

    return []


def _tool_event_markdown(
    name: str,
    args: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    round_idx: int | None = None,
    status: str | None = None,
    preview: str | None = None,
    policy: dict[str, Any] | None = None,
) -> str:
    parts: list[str] = [f"### `{name}`"]
    if round_idx is not None:
        parts.append(f"**{_t('tool_field_round')}** {_tf('round_label', round=round_idx)}")
    if status:
        parts.append(f"**{_t('tool_field_status')}** {status}")
    risk_label = _tool_policy_label(policy)
    risk_reason = _tool_policy_reason(policy)
    if risk_label:
        parts.append(f"**{_t('tool_field_risk')}** {risk_label}")
    if risk_reason:
        parts.append(f"**{_t('tool_field_why')}** {risk_reason}")
    if preview:
        parts.append(f"**{_t('tool_field_preview')}**")
        parts.append(_preview_markdown_block(preview))
    if args is not None:
        parts.append(f"**{_t('tool_field_input')}**")
        parts.append(f"```json\n{_pretty_json(args)}\n```")
    if result is not None:
        parts.append(f"**{_t('tool_field_result')}**")
        parts.append(f"```json\n{_pretty_json(result)}\n```")
    return "\n\n".join(parts)


def _single_line(text: str, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _tool_event_summary(
    name: str,
    status: str,
    args: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    preview: str | None = None,
    policy: dict[str, Any] | None = None,
) -> str:
    policy_prefix = ""
    risk_label = _tool_policy_label(policy)
    if risk_label:
        policy_prefix = f"[{risk_label}] "
    if isinstance(result, dict):
        if {"health", "score", "issue_count"} & set(result.keys()):
            health = str(result.get("health") or "unknown")
            score = result.get("score")
            issue_count = result.get("issue_count")
            parts = [f"health {health}"]
            if score is not None:
                parts.append(f"score {score}")
            if issue_count is not None:
                parts.append(f"{issue_count} issue(s)")
            return _single_line(", ".join(parts))
        summary = str(result.get("summary") or "").strip()
        if summary:
            return _single_line(summary)
        if result.get("rollback_id"):
            rollback_id = result.get("rollback_id")
            source_tool = str(result.get("source_tool") or "").strip()
            if source_tool:
                return _single_line(f"#{rollback_id} {source_tool}")
            return _single_line(f"rollback #{rollback_id}")
        error_text = str(result.get("error") or "").strip()
        if error_text:
            return _single_line(f"{_t('error_prefix')}：{error_text}")
        if result.get("source_path") and result.get("target_path"):
            return _single_line(f"{result['source_path']} -> {result['target_path']}")
        if result.get("command"):
            code = result.get("returncode")
            suffix = f" · exit {code}" if code is not None else ""
            return _single_line(f"$ {result['command']}{suffix}")
        if result.get("path"):
            path = str(result["path"])
            line_count = result.get("line_count")
            if isinstance(line_count, int) and line_count > 0:
                return _single_line(f"{path} · {line_count} lines")
            return _single_line(path)

    if preview:
        if isinstance(args, dict) and args.get("rollback_id"):
            return _single_line(f"rollback #{args['rollback_id']} preview")
        return _single_line(preview)

    if isinstance(args, dict):
        if args.get("source_path") and args.get("target_path"):
            return _single_line(f"{args['source_path']} -> {args['target_path']}")
        if args.get("command"):
            return _single_line(f"$ {args['command']}")
        if args.get("path"):
            return _single_line(str(args["path"]))
        if args.get("query"):
            return _single_line(f"{_t('search_prefix')}：{args['query']}")

    fallback = {
        _t("tool_status_preview"): _tf("tool_previewing", name=name),
        _t("tool_status_running"): _tf("tool_running", name=name),
        _t("tool_status_success"): _tf("tool_done", name=name),
        _t("tool_status_failed"): _tf("tool_failed", name=name),
    }
    return fallback.get(status, f"{name} {status}")


def _assistant_body_html(content: str, streaming: bool, thinking: bool) -> str:
    if thinking:
        body = f'<span class="typing">{html.escape(_t("thinking"))}</span>'
    elif streaming:
        body = html.escape(content).replace("\n", "<br>")
        if not body:
            body = f'<span class="typing">{html.escape(_t("thinking"))}</span>'
    else:
        body = render(content)
        if not body:
            body = f'<span class="typing">{html.escape(_t("preparing_reply"))}</span>'
    if streaming:
        body += '<span class="cursor">▍</span>'
    return body


def _looks_like_agent_task(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False

    lower = raw.lower()
    action_keywords = (
        "read file",
        "open file",
        "check file",
        "inspect file",
        "search file",
        "find file",
        "edit file",
        "modify file",
        "change file",
        "write file",
        "rename",
        "copy",
        "move file",
        "delete file",
        "delete folder",
        "create file",
        "create directory",
        "make directory",
        "run command",
        "terminal",
        "powershell",
        "cmd ",
        "bash ",
        "git ",
        "读取文件",
        "查看文件",
        "检查文件",
        "搜索文件",
        "查找文件",
        "编辑文件",
        "修改文件",
        "写入文件",
        "重命名",
        "复制",
        "改名",
        "移动文件",
        "删除文件",
        "删除目录",
        "创建文件",
        "创建目录",
        "新建目录",
        "运行命令",
        "执行命令",
        "终端",
        "命令行",
        "文件夹",
        "目录",
        "路径",
    )
    extra_keywords = (
        "rollback",
        "undo",
        "revert",
        "\u56de\u6eda",
        "\u64a4\u9500",
        "\u6062\u590d\u6539\u52a8",
    )
    if any(keyword in lower for keyword in action_keywords + extra_keywords):
        return True

    if any(marker in raw for marker in ("./", "../")):
        return True

    if re.search(r"[A-Za-z]:[\\/]", raw):
        return True

    if re.search(
        r"\.(py|js|ts|tsx|jsx|json|md|txt|yaml|yml|toml|ini|bat|ps1|sh|c|cc|cpp|h|hpp|java|go|rs)\b",
        lower,
    ):
        return True

    return False


class InputBox(QTextEdit):
    def __init__(self, on_send, slash_handler: Callable[[str, QEvent], bool] | None = None):
        super().__init__()
        self.setPlaceholderText(_t("input_hint"))
        self.setMinimumHeight(62)
        self.setMaximumHeight(88)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.on_send = on_send
        self.slash_handler = slash_handler

    def keyPressEvent(self, e):
        if self.slash_handler is not None and self.slash_handler(self.toPlainText(), e):
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            e.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.on_send()
            return
        super().keyPressEvent(e)


class MessageBody(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setStyleSheet("background: transparent; border: none;")
        self.document().setDocumentMargin(0)
        self.document().setDefaultStyleSheet(MESSAGE_BODY_STYLE)

    def set_content(self, html_text: str, width: int, text_color: str, streaming: bool = False):
        body = html_text or f'<span class="typing">{html.escape(_t("thinking"))}</span>'
        width = max(220, width)
        self.setUpdatesEnabled(False)
        try:
            self.document().setDefaultStyleSheet(MESSAGE_BODY_STYLE)
            self.setHtml(f'<div style="color: {text_color};">{body}</div>')
            self.document().setTextWidth(width)
            self.document().adjustSize()
            height = int(self.document().size().height()) + 24
            self.setFixedSize(width, max(34, height))
        finally:
            self.setUpdatesEnabled(True)
            self.viewport().update()


class MessageCard(QFrame):
    def __init__(
        self,
        role: str,
        content: str,
        created_at: str | None,
        width: int,
        streaming: bool = False,
        thinking: bool = False,
        error: bool = False,
    ):
        super().__init__()
        self.role = role
        self._width = width
        self._text_color = C_TEXT_MAIN if role == "assistant" else "#F8FAFC"
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setFixedWidth(width)

        if error:
            style = (
                "background: rgba(127, 29, 29, 0.20); "
                "border: 1px solid rgba(248, 113, 113, 0.34); "
                "border-radius: 20px;"
            )
            text_color = "#F8FAFC"
            role_color = "#FCA5A5"
            body_html = f'<div class="error-box">{html.escape(_t("error_prefix"))}：{html.escape(content)}</div>'
        elif role == "assistant":
            style = (
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                "stop:0 rgba(15, 23, 42, 0.96), stop:1 rgba(17, 24, 39, 0.98)); "
                "border: 1px solid rgba(34, 48, 71, 1); "
                "border-radius: 20px;"
            )
            if streaming or thinking:
                style = style.replace(
                    "rgba(34, 48, 71, 1)",
                    "rgba(124, 58, 237, 0.42)",
                )
            text_color = C_TEXT_MAIN
            self._text_color = text_color
            role_color = "#C4B5FD"
            body_html = _assistant_body_html(content, streaming=streaming, thinking=thinking)
        else:
            style = (
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                "stop:0 rgba(17, 24, 39, 0.98), stop:1 rgba(22, 32, 51, 0.98)); "
                "border: 1px solid rgba(37, 99, 235, 0.28); "
                "border-radius: 20px;"
            )
            text_color = "#F8FAFC"
            self._text_color = text_color
            role_color = "#93C5FD"
            body_html = html.escape(content).replace("\n", "<br>")

        self.setStyleSheet(style)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)

        role_label = QLabel("kagent" if role == "assistant" else _t("you"))
        role_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        role_label.setStyleSheet(f"color: {role_color};")

        time_label = QLabel(_format_message_time(created_at))
        time_label.setFont(QFont("Microsoft YaHei", 8))
        time_label.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER};")

        header.addWidget(role_label)
        header.addStretch(1)
        header.addWidget(time_label)
        layout.addLayout(header)

        self.body = MessageBody()
        self.body.set_content(body_html, max(220, width - 32), text_color=text_color, streaming=streaming)
        layout.addWidget(self.body)

    def update_body(self, content: str, streaming: bool = False, thinking: bool = False):
        if self.role != "assistant":
            return
        body_html = _assistant_body_html(content, streaming=streaming, thinking=thinking)
        self.body.set_content(
            body_html,
            max(220, self._width - 32),
            text_color=self._text_color,
            streaming=streaming,
        )


class ToolLogEntry(QFrame):
    approval_decided = pyqtSignal(str, bool)
    action_requested = pyqtSignal(object)

    def __init__(self, width: int, call_id: str, name: str, round_idx: int | None = None):
        super().__init__()
        self.call_id = call_id
        self._width = width
        self._preview: str | None = None
        self._policy: dict[str, Any] | None = None
        self._summary_full = _t("waiting_tool_output")
        self._approval_pending = False
        self._actions: list[dict[str, str]] = []
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setFixedWidth(width)
        self.setStyleSheet(
            "background: rgba(255, 255, 255, 0.018); "
            f"border: 1px solid {C_BORDER_SOFT}; border-radius: 12px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 9)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_btn.setToolTip(_t("tool_detail_expand"))
        self.toggle_btn.setAutoRaise(True)
        self.toggle_btn.clicked.connect(self._set_expanded)

        self.timeline_dot = QLabel("●")
        self.timeline_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timeline_dot.setFixedWidth(14)
        self.timeline_dot.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: 900;")

        self.name_label = QLabel(name)
        self.name_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: #F8FAFC;")

        self.round_label = QLabel("")
        self.round_label.setFont(QFont("Microsoft YaHei", 8))
        self.round_label.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER};")

        self.summary_label = QLabel(self._summary_full)
        self.summary_label.setFont(QFont("Microsoft YaHei", 8))
        self.summary_label.setStyleSheet(f"color: {C_TEXT_SUB};")
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.summary_label.setMinimumWidth(0)

        self.status_chip = QLabel(_t("tool_status_running"))
        self.status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.status_chip.setStyleSheet(
            "background: rgba(124, 58, 237, 0.16); color: #E9D5FF; "
            "border: 1px solid rgba(124, 58, 237, 0.30); "
            "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
        )

        self.risk_chip = QLabel("")
        self.risk_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.risk_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.risk_chip.setVisible(False)

        header.addWidget(self.timeline_dot)
        header.addWidget(self.toggle_btn)
        header.addWidget(self.name_label)
        if round_idx is not None:
            self.round_label.setText(_tf("round_label", round=round_idx))
            header.addWidget(self.round_label)
        header.addWidget(self.summary_label, 1)
        header.addStretch(1)
        header.addWidget(self.risk_chip)
        header.addWidget(self.status_chip)
        layout.addLayout(header)

        self.body = MessageBody()
        self.body.set_content(
            f'<span class="typing">{html.escape(_t("waiting_tool_output"))}</span>',
            max(220, width - 24),
            text_color=C_TEXT_MAIN,
        )
        self.body.setVisible(False)
        layout.addWidget(self.body)

        self.approval_bar = QWidget()
        approval_layout = QHBoxLayout(self.approval_bar)
        approval_layout.setContentsMargins(0, 0, 0, 0)
        approval_layout.setSpacing(8)

        self.approval_label = QLabel(_t("approval_required"))
        self.approval_label.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 12px;")

        self.allow_btn = QPushButton(_t("allow"))
        self.allow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.allow_btn.setStyleSheet(
            "background: rgba(34, 197, 94, 0.16); color: #DCFCE7; "
            "border: 1px solid rgba(34, 197, 94, 0.28); "
            "border-radius: 10px; padding: 6px 12px; font-size: 11px; font-weight: 700;"
        )
        self.allow_btn.clicked.connect(lambda: self._submit_approval(True))

        self.reject_btn = QPushButton(_t("reject"))
        self.reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reject_btn.setStyleSheet(
            "background: rgba(248, 113, 113, 0.14); color: #FECACA; "
            "border: 1px solid rgba(248, 113, 113, 0.24); "
            "border-radius: 10px; padding: 6px 12px; font-size: 11px; font-weight: 700;"
        )
        self.reject_btn.clicked.connect(lambda: self._submit_approval(False))

        approval_layout.addWidget(self.approval_label)
        approval_layout.addStretch(1)
        approval_layout.addWidget(self.allow_btn)
        approval_layout.addWidget(self.reject_btn)
        self.approval_bar.setVisible(False)
        layout.addWidget(self.approval_bar)

        self.actions_bar = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_bar)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        self.actions_bar.setVisible(False)
        layout.addWidget(self.actions_bar)

    def _refresh_summary_label(self) -> None:
        available = max(160, self.width() - 220)
        text = self.summary_label.fontMetrics().elidedText(
            self._summary_full,
            Qt.TextElideMode.ElideRight,
            available,
        )
        self.summary_label.setText(text)

    def _set_expanded(self, expanded: bool) -> None:
        self.body.setVisible(expanded)
        self.toggle_btn.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.toggle_btn.setToolTip(_t("tool_detail_collapse") if expanded else _t("tool_detail_expand"))
        self.updateGeometry()

    def _risk_chip_style(self, level: str) -> str:
        normalized = str(level or "").strip().lower()
        if normalized == "critical":
            return (
                "background: rgba(239, 68, 68, 0.18); color: #FECACA; "
                "border: 1px solid rgba(239, 68, 68, 0.34); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        if normalized == "high":
            return (
                "background: rgba(249, 115, 22, 0.18); color: #FED7AA; "
                "border: 1px solid rgba(249, 115, 22, 0.34); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        if normalized == "medium":
            return (
                "background: rgba(234, 179, 8, 0.16); color: #FEF08A; "
                "border: 1px solid rgba(234, 179, 8, 0.28); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        if normalized == "low":
            return (
                "background: rgba(34, 197, 94, 0.14); color: #BBF7D0; "
                "border: 1px solid rgba(34, 197, 94, 0.24); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        return (
            "background: rgba(148, 163, 184, 0.14); color: #CBD5E1; "
            "border: 1px solid rgba(148, 163, 184, 0.22); "
            "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
        )

    def _approval_prompt_text(self) -> str:
        risk_label = _tool_policy_label(self._policy)
        risk_reason = _tool_policy_reason(self._policy)
        if risk_label and risk_reason:
            return _tf("approval_required_detail", label=risk_label, reason=risk_reason)
        if risk_label:
            return _tf("approval_required_label_only", label=risk_label)
        return _t("approval_required")

    def _set_policy(self, policy: dict[str, Any] | None) -> None:
        self._policy = dict(policy) if isinstance(policy, dict) else None
        label = _tool_policy_label(self._policy)
        if not label:
            self.risk_chip.clear()
            self.risk_chip.setVisible(False)
            return
        self.risk_chip.setText(label)
        self.risk_chip.setStyleSheet(
            self._risk_chip_style(str((self._policy or {}).get("risk_level") or ""))
        )
        self.risk_chip.setVisible(True)

    def _submit_approval(self, approved: bool) -> None:
        if not self._approval_pending:
            return
        self._approval_pending = False
        self.allow_btn.setEnabled(False)
        self.reject_btn.setEnabled(False)
        self.approval_label.setText(
            _t("approved_continuing") if approved else _t("rejected_returning")
        )
        self.approval_decided.emit(self.call_id, approved)

    def _submit_action(self, action: dict[str, str]) -> None:
        if not isinstance(action, dict):
            return
        self.action_requested.emit(dict(action))

    def set_approval_pending(self, pending: bool) -> None:
        self._approval_pending = pending
        if pending:
            self.approval_label.setText(self._approval_prompt_text())
            self.allow_btn.setEnabled(True)
            self.reject_btn.setEnabled(True)
            self.approval_bar.setVisible(True)
        else:
            self.approval_bar.setVisible(False)
        self.updateGeometry()

    def set_actions(self, actions: list[dict[str, str]]) -> None:
        self._actions = [dict(action) for action in actions if isinstance(action, dict)]
        _clear_layout(self.actions_layout)
        if not self._actions:
            self.actions_bar.setVisible(False)
            self.updateGeometry()
            return

        title = QLabel(_t("quick_actions"))
        title.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 12px;")
        self.actions_layout.addWidget(title)

        for idx in range(0, len(self._actions), 2):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            for action in self._actions[idx : idx + 2]:
                btn = QPushButton(str(action.get("label") or _t("execute")))
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "background: rgba(255, 255, 255, 0.04); color: #E5E7EB; "
                    f"border: 1px solid {C_BORDER}; border-radius: 10px; "
                    "padding: 6px 12px; font-size: 11px; font-weight: 700;"
                )
                btn.clicked.connect(
                    lambda checked=False, payload=dict(action): self._submit_action(payload)
                )
                row.addWidget(btn)
            row.addStretch(1)
            self.actions_layout.addLayout(row)

        self.actions_bar.setVisible(True)
        self.updateGeometry()

    def set_event(
        self,
        status: str,
        args: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        round_idx: int | None = None,
        error: bool = False,
        preview: str | None = None,
        approval_pending: bool | None = None,
        policy: dict[str, Any] | None = None,
    ) -> None:
        if round_idx is not None:
            self.round_label.setText(_tf("round_label", round=round_idx))
        self.status_chip.setText(status)
        if preview is not None:
            self._preview = preview
        if policy is not None:
            self._set_policy(policy)
        status_key = status.strip().lower()
        if error or status_key in {"rejected", "failed"}:
            chip_style = (
                "background: rgba(248, 113, 113, 0.16); color: #FCA5A5; "
                "border: 1px solid rgba(248, 113, 113, 0.30); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        elif status in {_t("tool_status_success"), "成功", "Success"}:
            chip_style = (
                "background: rgba(34, 197, 94, 0.14); color: #BBF7D0; "
                "border: 1px solid rgba(34, 197, 94, 0.28); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        elif status in {_t("tool_status_failed"), "失败", "Failed"}:
            chip_style = (
                "background: rgba(248, 113, 113, 0.16); color: #FCA5A5; "
                "border: 1px solid rgba(248, 113, 113, 0.30); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        else:
            chip_style = (
                "background: rgba(56, 189, 248, 0.12); color: #BAE6FD; "
                "border: 1px solid rgba(56, 189, 248, 0.26); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        self.status_chip.setStyleSheet(chip_style)
        dot_color = "#F87171" if error or status_key in {"rejected", "failed"} else "#38BDF8"
        if status in {_t("tool_status_success"), "鎴愬姛", "Success"}:
            dot_color = "#22C55E"
        elif status in {_t("tool_status_failed"), "澶辫触", "Failed"}:
            dot_color = "#F87171"
        self.timeline_dot.setStyleSheet(f"color: {dot_color}; font-size: 12px; font-weight: 900;")
        self._summary_full = _tool_event_summary(
            self.name_label.text(),
            status,
            args=args,
            result=result,
            preview=self._preview,
            policy=self._policy,
        )
        self._refresh_summary_label()

        body_md = _tool_event_markdown(
            self.name_label.text(),
            args=args,
            result=result,
            round_idx=round_idx,
            status=status,
            preview=self._preview,
            policy=self._policy,
        )
        self.body.set_content(
            render(body_md),
            max(220, self._width - 24),
            text_color=C_TEXT_MAIN,
        )
        self.set_actions(_tool_entry_actions(self.name_label.text(), result=result))
        if approval_pending is not None:
            self.set_approval_pending(approval_pending)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_summary_label()


class ToolTraceCard(QFrame):
    approval_decided = pyqtSignal(str, bool)
    action_requested = pyqtSignal(object)

    def __init__(self, width: int):
        super().__init__()
        self._width = width
        self._entries: dict[str, ToolLogEntry] = {}
        self._run_id = ""
        self._run_log_path = ""
        self._trust: dict[str, Any] | None = None
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setFixedWidth(width)
        self.setStyleSheet(
            "background: rgba(8, 13, 22, 0.78); "
            f"border: 1px solid {C_BORDER_SOFT}; border-radius: 16px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel(_t("agent_run_log"))
        title.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #BAE6FD;")

        self.state_chip = QLabel(_t("tool_status_running"))
        self.state_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.state_chip.setStyleSheet(
            "background: rgba(56, 189, 248, 0.12); color: #BAE6FD; "
            "border: 1px solid rgba(56, 189, 248, 0.26); "
            "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
        )

        self.hint = QLabel(_t("waiting_tool_call"))
        self.hint.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 11px;")

        header.addWidget(title)
        header.addWidget(self.hint)
        header.addStretch(1)
        header.addWidget(self.state_chip)
        layout.addLayout(header)

        debug_row = QHBoxLayout()
        debug_row.setSpacing(8)
        self.run_meta_label = QLabel("")
        self.run_meta_label.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 11px;")
        self.run_meta_label.setWordWrap(True)
        debug_row.addWidget(self.run_meta_label, 1)

        self.run_summary_btn = QPushButton(_t("log_summary"))
        self.run_timeline_btn = QPushButton(_t("timeline"))
        self.run_review_btn = QPushButton(_t("run_review"))
        self.run_quality_gate_btn = QPushButton(_t("quality_gate"))
        self.run_bug_report_btn = QPushButton(_t("bug_report"))
        self.run_regression_plan_btn = QPushButton(_t("regression_plan"))
        for btn in (
            self.run_summary_btn,
            self.run_timeline_btn,
            self.run_review_btn,
            self.run_quality_gate_btn,
            self.run_bug_report_btn,
            self.run_regression_plan_btn,
        ):
            btn.setEnabled(False)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "background: rgba(255, 255, 255, 0.04); color: #CBD5E1; "
                f"border: 1px solid {C_BORDER}; border-radius: 10px; "
                "padding: 5px 9px; font-size: 11px; font-weight: 700;"
            )
            debug_row.addWidget(btn)
        self.run_summary_btn.clicked.connect(lambda: self._request_run_debug("summary"))
        self.run_timeline_btn.clicked.connect(lambda: self._request_run_debug("timeline"))
        self.run_review_btn.clicked.connect(lambda: self._request_run_debug("review"))
        self.run_quality_gate_btn.clicked.connect(lambda: self._request_run_debug("quality_gate"))
        self.run_bug_report_btn.clicked.connect(lambda: self._request_run_debug("bug_report"))
        self.run_regression_plan_btn.clicked.connect(lambda: self._request_run_debug("regression_plan"))
        layout.addLayout(debug_row)

        self.plan_card = QFrame()
        self.plan_card.setStyleSheet(
            "background: rgba(255, 255, 255, 0.018); "
            f"border: 1px solid {C_BORDER_SOFT}; border-radius: {C_RADIUS_MD}px;"
        )
        plan_layout = QVBoxLayout(self.plan_card)
        plan_layout.setContentsMargins(10, 8, 10, 9)
        plan_layout.setSpacing(5)
        self.plan_title = QLabel(_t("agent_plan"))
        self.plan_title.setStyleSheet("color: #BAE6FD; font-size: 11px; font-weight: 800;")
        self.plan_body = QLabel(_t("agent_plan_waiting"))
        self.plan_body.setWordWrap(True)
        self.plan_body.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 11px;")
        plan_layout.addWidget(self.plan_title)
        plan_layout.addWidget(self.plan_body)
        self.plan_card.setVisible(False)
        layout.addWidget(self.plan_card)

        self.entries_layout = QVBoxLayout()
        self.entries_layout.setSpacing(6)
        layout.addLayout(self.entries_layout)

        self.empty_label = QLabel(_t("agent_analyzing_tools"))
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 12px;")
        layout.addWidget(self.empty_label)

    def set_run_info(self, run_id: str, run_log_path: str) -> None:
        self._run_id = str(run_id or "")
        self._run_log_path = str(run_log_path or "")
        self.run_summary_btn.setEnabled(bool(self._run_log_path))
        self.run_timeline_btn.setEnabled(bool(self._run_log_path))
        self.run_review_btn.setEnabled(bool(self._run_log_path))
        self.run_quality_gate_btn.setEnabled(bool(self._run_log_path))
        self.run_bug_report_btn.setEnabled(bool(self._run_log_path))
        self.run_regression_plan_btn.setEnabled(bool(self._run_log_path))
        self._refresh_run_meta()

    def set_trust_summary(self, trust: dict[str, Any]) -> None:
        self._trust = dict(trust)
        self._refresh_run_meta()

    def set_plan(self, plan: list[dict[str, Any]]) -> None:
        lines = _plan_steps_summary(plan)
        self.plan_body.setText("\n".join(lines) if lines else _t("agent_plan_waiting"))
        self.plan_card.setVisible(bool(lines))

    def _refresh_run_meta(self) -> None:
        parts = []
        if self._run_id:
            parts.append(f"run: {self._run_id[:10]}")
        if self._trust:
            health = str(self._trust.get("health") or "unknown")
            validated = _t("validated_yes") if self._trust.get("validated") else _t("validated_no")
            parts.append(f"health: {health}")
            parts.append(f"validated: {validated}")
        self.run_meta_label.setText(" | ".join(parts) if parts else _t("waiting_run_log"))

    def _request_run_debug(self, mode: str) -> None:
        self.action_requested.emit(
            {
                "action": "show_run_debug",
                "mode": mode,
                "run_id": self._run_id,
                "run_log_path": self._run_log_path,
            }
        )

    def _sync_empty(self):
        has_entries = bool(self._entries)
        self.empty_label.setVisible(not has_entries)
        self.hint.setVisible(not has_entries)

    def set_state(self, text: str, kind: str = "active") -> None:
        self.state_chip.setText(text)
        if kind == "done":
            style = (
                "background: rgba(34, 197, 94, 0.14); color: #BBF7D0; "
                "border: 1px solid rgba(34, 197, 94, 0.28); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        elif kind == "error":
            style = (
                "background: rgba(248, 113, 113, 0.16); color: #FCA5A5; "
                "border: 1px solid rgba(248, 113, 113, 0.30); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        else:
            style = (
                "background: rgba(56, 189, 248, 0.12); color: #BAE6FD; "
                "border: 1px solid rgba(56, 189, 248, 0.26); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        self.state_chip.setStyleSheet(style)

    def _forward_approval_decision(self, call_id: str, approved: bool) -> None:
        self.approval_decided.emit(call_id, approved)

    def _forward_action_request(self, action: object) -> None:
        self.action_requested.emit(action)

    def upsert_event(
        self,
        call_id: str,
        name: str,
        status: str,
        args: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        round_idx: int | None = None,
        error: bool = False,
        preview: str | None = None,
        approval_pending: bool | None = None,
        policy: dict[str, Any] | None = None,
    ) -> ToolLogEntry:
        entry = self._entries.get(call_id)
        if entry is None:
            entry = ToolLogEntry(max(260, self._width - 28), call_id, name, round_idx=round_idx)
            entry.approval_decided.connect(self._forward_approval_decision)
            entry.action_requested.connect(self._forward_action_request)
            self._entries[call_id] = entry
            self.entries_layout.addWidget(entry)
            self.empty_label.setVisible(False)
            self.hint.setVisible(False)
        entry.set_event(
            status,
            args=args,
            result=result,
            round_idx=round_idx,
            error=error,
            preview=preview,
            approval_pending=approval_pending,
            policy=policy,
        )
        self._sync_empty()
        return entry


class PermissionSettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(_t("settings_title"))
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        title = QLabel(_t("settings_heading"))
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_TEXT_MAIN};")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.language = self._language_combo(app_config.APP_LANGUAGE)

        form.addRow(_t("language"), self.language)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet("")
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText(_t("save"))
        if cancel_button is not None:
            cancel_button.setText(_t("cancel"))
        layout.addWidget(buttons)

    @staticmethod
    def _language_combo(value: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem(_t("language_zh"), "zh")
        combo.addItem(_t("language_en"), "en")
        current = _language_code(value)
        for idx in range(combo.count()):
            if combo.itemData(idx) == current:
                combo.setCurrentIndex(idx)
                break
        combo.setStyleSheet(
            f"background: {C_BG_INPUT}; color: {C_TEXT_MAIN}; border: 1px solid {C_BORDER}; "
            "border-radius: 8px; padding: 6px 8px;"
        )
        return combo

    def values(self) -> dict[str, str]:
        return {
            "APP_LANGUAGE": str(self.language.currentData() or "zh"),
        }


class CommandPaletteDialog(QDialog):
    def __init__(self, commands: list[dict[str, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self._commands = [dict(command) for command in commands]
        self.selected_action: str | None = None
        self.setWindowTitle(_t("command_palette"))
        self.setModal(True)
        self.resize(520, 420)
        self.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)

        title = QLabel(_t("command_palette"))
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 14px; font-weight: 800;")
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText(_t("command_palette_placeholder"))
        self.search.setStyleSheet(
            f"background: {C_BG_INPUT}; color: {C_TEXT_MAIN}; "
            f"border: 1px solid {C_BORDER}; border-radius: {C_RADIUS_MD}px; "
            "padding: 9px 11px; font-size: 13px;"
        )
        self.search.textChanged.connect(self._refresh)
        layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            f"""
QListWidget {{
    background: {C_BG_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: {C_RADIUS_LG}px;
    color: {C_TEXT_MAIN};
    outline: none;
    font-size: 13px;
}}
QListWidget::item {{
    padding: 10px 12px;
    margin: 3px;
    border-radius: {C_RADIUS_MD}px;
}}
QListWidget::item:selected {{
    background: rgba(56, 189, 248, 0.14);
    color: #E0F2FE;
}}
""".strip()
        )
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_current())
        layout.addWidget(self.list_widget, 1)

        self.search.returnPressed.connect(self._accept_current)
        self._refresh("")
        self.search.setFocus()

    def _refresh(self, query: str) -> None:
        query = str(query or "").strip().lower()
        self.list_widget.clear()
        for command in self._commands:
            label = str(command.get("label") or "")
            keywords = str(command.get("keywords") or "")
            haystack = f"{label} {keywords}".lower()
            if query and query not in haystack:
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(command.get("action") or ""))
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _accept_current(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_action = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self.accept()


class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("kagent")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        self.current_session: str | None = None
        self.worker: AgentWorker | None = None
        self._detached_workers: list[AgentWorker] = []
        self._streaming_buf = ""
        self._streaming_time = ""
        self._activity = "Ready"
        self._send_locked = False
        self._stop_requested = False
        self._agent_trace_card: ToolTraceCard | None = None
        self._agent_trace_row: QWidget | None = None
        self._tool_trace_events: list[dict[str, Any]] = []
        self._rollback_history_visible = False
        self._rollback_history_items: list[dict[str, Any]] = []
        self._selected_rollback_id: int | None = None
        self._render_seq = 0
        self._drag_start_global: QPoint | None = None
        self._drag_start_frame: QPoint | None = None
        preferences = load_ui_preferences()
        self._selected_model = preferences.get("model") or MODEL
        self._selected_reasoning_effort = normalize_reasoning_effort(
            preferences.get("reasoning_effort") or REASONING_EFFORT
        )

        root = QWidget()
        root.setObjectName("root")
        root.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {C_BG_ROOT}, stop:0.45 {C_BG_PANEL}, stop:1 #05070D);"
        )
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = self._build_title_bar()
        layout.addWidget(self.title_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_chat_area())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([264, 920])
        layout.addWidget(splitter, 1)

        layout.addWidget(self._build_status_bar())

        self.new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_shortcut.activated.connect(self.new_session)

        self.command_palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.command_palette_shortcut.activated.connect(self._open_command_palette)

        self.delete_shortcut = QShortcut(QKeySequence("Delete"), self.session_list)
        self.delete_shortcut.activated.connect(self._delete_current_session)

        self._load_sessions()
        sessions = db.list_sessions()
        if sessions:
            self._open_session(sessions[0]["id"])
        else:
            self._render_messages([])

        self._apply_language_texts()
        self._refresh_chat_header()
        self._update_status()

    # ==================== UI ====================

    def _build_title_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("windowTitleBar")
        bar.setFixedHeight(46)
        bar.setStyleSheet(
            f"background: rgba(5, 7, 13, 0.96); border-bottom: 1px solid {C_BORDER_SOFT};"
        )

        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(10)

        brand = QLabel("K")
        brand.setFixedSize(24, 24)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}); color: #fff; "
            "border-radius: 8px; font-size: 12px; font-weight: 800;"
        )
        h.addWidget(brand)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        title_stack.setContentsMargins(0, 0, 0, 0)

        title = QLabel("kagent")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_TEXT_MAIN};")

        self.sidebar_subtitle_label = QLabel(_t("local_coding_workspace"))
        self.sidebar_subtitle_label.setFont(QFont("Microsoft YaHei", 8))
        self.sidebar_subtitle_label.setStyleSheet(f"color: {C_TEXT_SUB};")

        title_stack.addWidget(title)
        title_stack.addWidget(self.sidebar_subtitle_label)
        h.addLayout(title_stack)
        h.addStretch(1)

        self.minimize_btn = self._window_control_button("-", "Minimize")
        self.maximize_btn = self._window_control_button("[]", "Maximize")
        self.close_btn = self._window_control_button("×", "Close", danger=True)
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.maximize_btn.clicked.connect(self._toggle_window_maximized)
        self.close_btn.clicked.connect(self.close)
        h.addWidget(self.minimize_btn)
        h.addWidget(self.maximize_btn)
        h.addWidget(self.close_btn)

        return bar

    def _window_control_button(self, text: str, tooltip: str, *, danger: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setFixedSize(32, 28)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        hover = "rgba(248, 113, 113, 0.24)" if danger else "rgba(56, 189, 248, 0.14)"
        color = "#FCA5A5" if danger else C_TEXT_SUB
        button.setStyleSheet(
            "QPushButton {"
            "background: transparent;"
            f"color: {color};"
            "border: none;"
            "border-radius: 8px;"
            "font-size: 15px;"
            "font-weight: 800;"
            "}"
            "QPushButton:hover {"
            f"background: {hover};"
            f"color: {C_TEXT_MAIN};"
            "}"
        )
        return button

    def _toggle_window_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self.maximize_btn.setText("[]")
        else:
            self.showMaximized()
            self.maximize_btn.setText("][")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(264)
        sidebar.setStyleSheet(
            f"background: rgba(7, 11, 18, 0.96); border-right: 1px solid {C_BORDER_SOFT};"
        )

        v = QVBoxLayout(sidebar)
        v.setContentsMargins(10, 12, 10, 10)
        v.setSpacing(8)

        self.new_btn = QPushButton(_t("new_chat"))
        self.new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_btn.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}); "
            "color: #03111A; border: none; border-radius: 12px; padding: 10px 12px; "
            "font-size: 13px; font-weight: 800;"
        )
        self.new_btn.clicked.connect(self.new_session)
        v.addWidget(self.new_btn)

        self.new_folder_btn = QPushButton(_t("new_chat_for_folder"))
        self.new_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_folder_btn.setToolTip(_t("select_workspace_for_new_chat"))
        self.new_folder_btn.setStyleSheet(
            "background: rgba(255, 255, 255, 0.025); color: #CBD5E1; "
            f"border: 1px solid {C_BORDER}; border-radius: 12px; "
            "padding: 9px 12px; font-size: 12px; font-weight: 700;"
        )
        self.new_folder_btn.clicked.connect(self.new_session_from_folder)
        v.addWidget(self.new_folder_btn)

        self.session_list = QListWidget()
        self.session_list.setSpacing(4)
        self.session_list.setStyleSheet(
            f"""
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
    color: {C_TEXT_MAIN};
    font-size: 13px;
    font-family: "Microsoft YaHei", "Segoe UI";
}}
QListWidget::item {{
    padding: 10px 11px;
    margin: 3px 2px;
    border-radius: 10px;
}}
QListWidget::item:hover {{
    background: rgba(255, 255, 255, 0.035);
}}
QListWidget::item:selected {{
    background: rgba(56, 189, 248, 0.16);
    color: #E0F2FE;
}}
""".strip()
        )
        self.session_list.itemClicked.connect(self._on_session_clicked)
        v.addWidget(self.session_list, 1)

        self.sidebar_tip_label = QLabel(_t("sidebar_shortcuts"))
        self.sidebar_tip_label.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 11px; padding: 4px 2px;")
        self.sidebar_tip_label.setVisible(False)

        return sidebar

    def _build_chat_area(self) -> QFrame:
        main = QFrame()
        main.setObjectName("chatArea")
        main.setStyleSheet("background: transparent;")

        v = QVBoxLayout(main)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._build_chat_header())

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_scroll.setStyleSheet(
            f"""
QScrollArea {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {C_BG_PANEL_ALT}, stop:1 {C_BG_PANEL});
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 14px 4px 14px 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(148, 163, 184, 0.28);
    border-radius: 5px;
    min-height: 36px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(148, 163, 184, 0.44);
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
""".strip()
        )

        self.chat_content = QWidget()
        self.chat_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.chat_content.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(28, 24, 28, 24)
        self.chat_layout.setSpacing(12)
        self.chat_scroll.setWidget(self.chat_content)
        self.chat_scroll.verticalScrollBar().valueChanged.connect(self._update_scroll_to_bottom_button)
        self.chat_scroll.verticalScrollBar().rangeChanged.connect(self._update_scroll_to_bottom_button)
        self.chat_scroll.viewport().installEventFilter(self)

        self.scroll_bottom_btn = QPushButton("↓", self.chat_scroll.viewport())
        self.scroll_bottom_btn.setFixedSize(38, 38)
        self.scroll_bottom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scroll_bottom_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll_bottom_btn.setToolTip(_t("scroll_bottom"))
        self.scroll_bottom_btn.clicked.connect(self._scroll_to_bottom)
        self.scroll_bottom_btn.setStyleSheet(
            "QPushButton {"
            "background: rgba(15, 23, 42, 0.92);"
            "color: #E2E8F0;"
            "border: 1px solid rgba(148, 163, 184, 0.24);"
            "border-radius: 19px;"
            "font-size: 18px;"
            "font-weight: 800;"
            "}"
            "QPushButton:hover {"
            "background: rgba(37, 99, 235, 0.22);"
            "border: 1px solid rgba(96, 165, 250, 0.45);"
            "}"
            "QPushButton:pressed {"
            "background: rgba(59, 130, 246, 0.30);"
            "}"
        )
        self.scroll_bottom_btn.hide()
        self.scroll_bottom_btn.raise_()

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.chat_scroll, 1)
        body_layout.addWidget(self._build_rollback_panel())
        v.addWidget(body, 1)

        v.addWidget(self._build_input_bar())
        return main

    def _build_rollback_panel(self) -> QFrame:
        panel = QFrame()
        panel.setFixedWidth(360)
        panel.setVisible(False)
        panel.setStyleSheet(
            f"background: rgba(9, 16, 27, 0.96); border-left: 1px solid {C_BORDER};"
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self.rollback_history_title_label = QLabel(_t("rollback_history_title"))
        self.rollback_history_title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.rollback_history_title_label.setStyleSheet(f"color: {C_TEXT_MAIN};")
        header.addWidget(self.rollback_history_title_label)

        self.rollback_count_label = QLabel(f"0 {_t('entries')}")
        self.rollback_count_label.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 11px;")
        header.addWidget(self.rollback_count_label)
        header.addStretch(1)

        self.rollback_refresh_btn = QPushButton(_t("refresh"))
        self.rollback_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_refresh_btn.clicked.connect(self._refresh_rollback_history_panel)
        self.rollback_refresh_btn.setStyleSheet(
            "background: rgba(255, 255, 255, 0.04); color: #E5E7EB; "
            f"border: 1px solid {C_BORDER}; border-radius: 10px; "
            "padding: 6px 10px; font-size: 11px; font-weight: 700;"
        )
        header.addWidget(self.rollback_refresh_btn)

        self.rollback_back_activity_btn = QPushButton(_t("activity_back_to_activity"))
        self.rollback_back_activity_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_back_activity_btn.clicked.connect(self._return_rollback_history_to_activity)
        self.rollback_back_activity_btn.setStyleSheet(_button_style("secondary", compact=True))
        header.addWidget(self.rollback_back_activity_btn)

        layout.addLayout(header)

        self.rollback_list = QListWidget()
        self.rollback_list.setSpacing(4)
        self.rollback_list.setStyleSheet(
            f"""
QListWidget {{
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid {C_BORDER};
    border-radius: 16px;
    outline: none;
    color: {C_TEXT_MAIN};
    font-size: 12px;
    font-family: "Microsoft YaHei", "Segoe UI";
}}
QListWidget::item {{
    padding: 10px 12px;
    margin: 4px 4px;
    border-radius: 12px;
}}
QListWidget::item:hover {{
    background: rgba(255, 255, 255, 0.04);
}}
QListWidget::item:selected {{
    background: rgba(37, 99, 235, 0.18);
    color: #EFF6FF;
}}
""".strip()
        )
        self.rollback_list.itemSelectionChanged.connect(self._on_rollback_item_selection_changed)
        layout.addWidget(self.rollback_list, 1)

        detail_card = QFrame()
        detail_card.setStyleSheet(
            "background: rgba(15, 23, 42, 0.92); "
            f"border: 1px solid {C_BORDER}; border-radius: 18px;"
        )
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(14, 12, 14, 14)
        detail_layout.setSpacing(8)

        self.rollback_detail_title = QLabel(_t("rollback_select"))
        self.rollback_detail_title.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self.rollback_detail_title.setStyleSheet(f"color: {C_TEXT_MAIN};")
        detail_layout.addWidget(self.rollback_detail_title)

        self.rollback_detail_meta = QLabel(_t("rollback_meta_empty"))
        self.rollback_detail_meta.setWordWrap(True)
        self.rollback_detail_meta.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 11px;")
        detail_layout.addWidget(self.rollback_detail_meta)

        self.rollback_detail_files = QLabel("")
        self.rollback_detail_files.setWordWrap(True)
        self.rollback_detail_files.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 11px;")
        detail_layout.addWidget(self.rollback_detail_files)

        self.rollback_detail_body = QTextBrowser()
        self.rollback_detail_body.setFrameShape(QFrame.Shape.NoFrame)
        self.rollback_detail_body.setReadOnly(True)
        self.rollback_detail_body.setOpenExternalLinks(False)
        self.rollback_detail_body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rollback_detail_body.document().setDocumentMargin(0)
        self.rollback_detail_body.document().setDefaultStyleSheet(MESSAGE_BODY_STYLE)
        self.rollback_detail_body.setStyleSheet(
            "background: rgba(11, 17, 32, 0.88); border: 1px solid rgba(34, 48, 71, 1); "
            "border-radius: 14px; padding: 8px;"
        )
        self.rollback_detail_body.setMinimumHeight(220)
        detail_layout.addWidget(self.rollback_detail_body, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self.rollback_open_trace_btn = QPushButton(_t("open_in_chat"))
        self.rollback_open_trace_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_open_trace_btn.clicked.connect(self._open_selected_rollback_preview_in_chat)
        self.rollback_open_trace_btn.setStyleSheet(
            "background: rgba(255, 255, 255, 0.04); color: #E5E7EB; "
            f"border: 1px solid {C_BORDER}; border-radius: 10px; "
            "padding: 7px 12px; font-size: 11px; font-weight: 700;"
        )
        actions.addWidget(self.rollback_open_trace_btn)

        self.rollback_restore_btn = QPushButton(_t("restore"))
        self.rollback_restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_restore_btn.clicked.connect(self._restore_selected_rollback)
        self.rollback_restore_btn.setStyleSheet(
            "background: rgba(56, 189, 248, 0.14); color: #BAE6FD; "
            "border: 1px solid rgba(56, 189, 248, 0.32); border-radius: 10px; "
            "padding: 7px 12px; font-size: 11px; font-weight: 700;"
        )
        actions.addWidget(self.rollback_restore_btn)
        detail_layout.addLayout(actions)

        layout.addWidget(detail_card)

        self.rollback_panel = panel
        self._set_rollback_detail_empty()
        return panel

    def _build_chat_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet(
            f"background: rgba(8, 13, 22, 0.88); border-bottom: 1px solid {C_BORDER_SOFT};"
        )

        h = QHBoxLayout(header)
        h.setContentsMargins(22, 10, 22, 10)
        h.setSpacing(10)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        title_stack.setContentsMargins(0, 0, 0, 0)

        self.chat_title_label = QLabel(_t("new_session"))
        self.chat_title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.chat_title_label.setStyleSheet(f"color: {C_TEXT_MAIN};")

        self.chat_subtitle_label = QLabel(f"{self._model_reasoning_label()} | {_t('workspace')} | 0 {_t('messages')} | {_t('ready')}")
        self.chat_subtitle_label.setFont(QFont("Microsoft YaHei", 8))
        self.chat_subtitle_label.setStyleSheet(f"color: {C_TEXT_SUB};")

        self.chat_subtitle_label.setText(
            f"{self._model_reasoning_label()} | {_t('workspace')} | 0 {_t('messages')} | {_t('ready')}"
        )

        title_stack.addWidget(self.chat_title_label)
        title_stack.addWidget(self.chat_subtitle_label)
        h.addLayout(title_stack)
        h.addStretch(1)

        self.activity_btn = QPushButton(_t("activity"))
        self.activity_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activity_btn.setToolTip(_t("activity_tip"))
        self.activity_btn.clicked.connect(self._show_activity_panel)
        self.activity_btn.setStyleSheet(_button_style("secondary", compact=True))
        h.addWidget(self.activity_btn)

        self._sync_rollback_history_button_style()

        self.chat_model_chip = _chip_label(self._model_reasoning_label(), "#BAE6FD", "rgba(56, 189, 248, 0.12)", "rgba(56, 189, 248, 0.28)")
        self.chat_mode_chip = _chip_label("Chat", "#CCFBF1", "rgba(20, 184, 166, 0.12)", "rgba(20, 184, 166, 0.28)")
        self.chat_mode_chip.setText(_t("workspace"))
        self.chat_mode_chip.setStyleSheet(
            "background: rgba(20, 184, 166, 0.12); color: #CCFBF1; "
            "border: 1px solid rgba(20, 184, 166, 0.30); border-radius: 999px; "
            "padding: 4px 10px; font-size: 11px; font-weight: 700;"
        )
        self.chat_model_chip.setVisible(False)
        h.addWidget(self.chat_model_chip)
        h.addWidget(self.chat_mode_chip)

        return header

    def _build_input_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(118)
        self.input_bar = bar
        bar.setStyleSheet(f"background: rgba(5, 7, 13, 0.96); border-top: 1px solid {C_BORDER_SOFT};")

        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 12, 18, 14)
        h.setSpacing(12)

        wrap = QFrame()
        self.input_wrap = wrap
        wrap.setStyleSheet(
            f"background: rgba(13, 22, 36, 0.94); border: 1px solid {C_BORDER}; border-radius: 18px;"
        )

        w = QVBoxLayout(wrap)
        w.setContentsMargins(15, 12, 15, 10)
        w.setSpacing(8)

        self.slash_command_list = QListWidget()
        self.slash_command_list.setVisible(False)
        self.slash_command_list.setMaximumHeight(178)
        self.slash_command_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.slash_command_list.setStyleSheet(
            f"""
QListWidget {{
    background: rgba(8, 13, 22, 0.98);
    border: 1px solid {C_BORDER};
    border-radius: 14px;
    color: {C_TEXT_MAIN};
    font-size: 11px;
    padding: 5px;
}}
QListWidget::item {{
    padding: 5px 10px;
    min-height: 24px;
    border-radius: 9px;
}}
QListWidget::item:hover {{
    background: rgba(56, 189, 248, 0.10);
}}
QListWidget::item:selected {{
    background: rgba(56, 189, 248, 0.18);
    color: #E0F2FE;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 8px 4px 8px 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(148, 163, 184, 0.28);
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(148, 163, 184, 0.44);
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
""".strip()
        )
        self.slash_command_list.itemClicked.connect(self._apply_slash_command_item)
        w.addWidget(self.slash_command_list)

        self.input = InputBox(self.on_send, slash_handler=self._handle_input_slash_key)
        self.input.setStyleSheet(
            f"background: transparent; border: none; color: {C_TEXT_MAIN}; "
            f"selection-background-color: rgba(56, 189, 248, 0.24); "
            "font-size: 14px; font-family: 'Microsoft YaHei', 'Segoe UI';"
        )
        self.input.textChanged.connect(self._refresh_slash_commands)
        w.addWidget(self.input)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        hint = QLabel(_t("input_shortcut_hint"))
        hint.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 11px;")
        self.input_hint_label = hint
        actions.addWidget(hint)
        actions.addStretch(1)

        self.agent_btn = QPushButton("Agent")
        self.agent_btn.setCheckable(True)
        self.agent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.agent_btn.setToolTip(_t("agent_mode_tip"))
        self.agent_btn.toggled.connect(self._sync_mode_button_style)
        self.agent_btn.toggled.connect(self._refresh_chat_header)
        self.agent_btn.setChecked(True)
        self.agent_btn.setVisible(False)
        actions.addWidget(self.agent_btn)
        self._sync_mode_button_style()

        self.permission_menu_btn = QPushButton(_t("permissions"))
        self.permission_menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.permission_menu_btn.setStyleSheet(_button_style("pill", compact=True))
        self.permission_menu_btn.clicked.connect(self._show_permission_menu)
        actions.addWidget(self.permission_menu_btn)

        self.workspace_btn = QPushButton(_workspace_button_label(self._current_workspace_root()))
        self.workspace_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.workspace_btn.setToolTip(
            _tf("workspace_button_tooltip", path=self._current_workspace_root())
        )
        self.workspace_btn.clicked.connect(self._show_workspace_menu)
        self.workspace_btn.setStyleSheet(_button_style("pill", compact=True))
        actions.addWidget(self.workspace_btn)

        self.send_btn = QPushButton(_t("send"))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.on_send)
        actions.addWidget(self.send_btn)

        self.stop_btn = QPushButton(_t("stop"))
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        actions.addWidget(self.stop_btn)
        self._sync_send_button_style()
        self._sync_stop_button_style()

        w.addLayout(actions)
        h.addWidget(wrap, 1)
        return bar

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(24)
        bar.setStyleSheet(f"background: rgba(5, 7, 13, 0.96); border-top: 1px solid {C_BORDER_SOFT};")

        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 16, 0)

        self.status_model = _chip_label(self._model_reasoning_label(), "#F5F3FF", "rgba(124, 58, 237, 0.16)", "rgba(124, 58, 237, 0.34)")
        self.status_model.setVisible(False)
        h.addWidget(self.status_model)
        h.addStretch(1)

        self.status_count = QLabel("")
        self.status_count.setObjectName("statusText")
        self.status_count.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 11.5px;")
        h.addWidget(self.status_count)

        grip = QSizeGrip(bar)
        grip.setFixedSize(14, 14)
        grip.setStyleSheet(f"background: transparent; color: {C_TEXT_SUB};")
        h.addWidget(grip)

        return bar

    def _sync_rollback_history_button_style(self) -> None:
        if not hasattr(self, "rollback_history_btn"):
            return
        self.rollback_history_btn.setText(_t("history"))
        if self._rollback_history_visible:
            self.rollback_history_btn.setStyleSheet(
                "background: rgba(56, 189, 248, 0.14); color: #BAE6FD; "
                "border: 1px solid rgba(56, 189, 248, 0.34); border-radius: 12px; "
                "padding: 7px 11px; font-size: 12px; font-weight: 700;"
            )
        else:
            self.rollback_history_btn.setStyleSheet(
                "background: rgba(255, 255, 255, 0.025); color: #94A3B8; "
                f"border: 1px solid {C_BORDER}; border-radius: 12px; "
                "padding: 7px 11px; font-size: 12px; font-weight: 700;"
            )

    def _activity_label(self) -> str:
        mapping = {
            "Ready": _t("ready"),
            "Working": _t("working"),
            "Stopping": _t("stopping_status"),
            "Stopped": _t("stopped"),
        }
        return mapping.get(self._activity, self._activity)

    def _permission_summary(self) -> str:
        return (
            f"{_t('read_permission')}: {self._scope_label(app_config.FILESYSTEM_READ_SCOPE)} | "
            f"{_t('write_permission')}: {self._scope_label(app_config.FILESYSTEM_WRITE_SCOPE)} | "
            f"{_t('command_permission')}: {self._scope_label(app_config.FILESYSTEM_COMMAND_SCOPE)}"
        )

    def _apply_language_texts(self) -> None:
        self.setWindowTitle("kagent")
        if hasattr(self, "new_btn"):
            self.new_btn.setText(_t("new_chat"))
        if hasattr(self, "new_folder_btn"):
            self.new_folder_btn.setText(_t("new_chat_for_folder"))
        if hasattr(self, "sidebar_subtitle_label"):
            self.sidebar_subtitle_label.setText(_t("local_coding_workspace"))
        if hasattr(self, "sidebar_tip_label"):
            self.sidebar_tip_label.setText(_t("sidebar_shortcuts"))
        if hasattr(self, "settings_btn"):
            self.settings_btn.setText(_t("settings"))
        if hasattr(self, "workspace_btn"):
            self.workspace_btn.setText(_workspace_button_label(self._current_workspace_root()))
            self.workspace_btn.setToolTip(
                _tf("workspace_button_tooltip", path=self._current_workspace_root())
                if self._current_workspace_root()
                else _t("no_project_tooltip")
            )
        if hasattr(self, "permission_menu_btn"):
            self.permission_menu_btn.setText(_t("permissions"))
        if hasattr(self, "rollback_history_btn"):
            self.rollback_history_btn.setText(_t("history"))
            self.rollback_history_btn.setToolTip(_t("rollback_history_tip"))
        if hasattr(self, "activity_btn"):
            self.activity_btn.setText(_t("activity"))
            self.activity_btn.setToolTip(_t("activity_tip"))
        if hasattr(self, "rollback_refresh_btn"):
            self.rollback_refresh_btn.setText(_t("refresh"))
        if hasattr(self, "rollback_back_activity_btn"):
            self.rollback_back_activity_btn.setText(_t("activity_back_to_activity"))
        if hasattr(self, "rollback_history_title_label"):
            self.rollback_history_title_label.setText(_t("rollback_history_title"))
        if hasattr(self, "rollback_open_trace_btn"):
            self.rollback_open_trace_btn.setText(_t("open_in_chat"))
        if hasattr(self, "rollback_restore_btn"):
            self.rollback_restore_btn.setText(_t("restore"))
        if hasattr(self, "input"):
            self.input.setPlaceholderText(_t("input_hint"))
            self._refresh_slash_commands()
        if hasattr(self, "input_hint_label"):
            self.input_hint_label.setText(_t("input_shortcut_hint"))
        if hasattr(self, "agent_btn"):
            self.agent_btn.setToolTip(_t("agent_mode_tip"))
        if hasattr(self, "send_btn"):
            self.send_btn.setText(_t("send"))
        if hasattr(self, "stop_btn"):
            self.stop_btn.setText(_t("stopping") if self._stop_requested else _t("stop"))
        if hasattr(self, "run_summary_btn"):
            self.run_summary_btn.setText(_t("log_summary"))
        if hasattr(self, "run_timeline_btn"):
            self.run_timeline_btn.setText(_t("timeline"))
        if hasattr(self, "run_review_btn"):
            self.run_review_btn.setText(_t("run_review"))
        if hasattr(self, "run_quality_gate_btn"):
            self.run_quality_gate_btn.setText(_t("quality_gate"))
        if hasattr(self, "run_bug_report_btn"):
            self.run_bug_report_btn.setText(_t("bug_report"))
        if hasattr(self, "run_regression_plan_btn"):
            self.run_regression_plan_btn.setText(_t("regression_plan"))
        if hasattr(self, "scroll_bottom_btn"):
            self.scroll_bottom_btn.setToolTip(_t("scroll_bottom"))
        if hasattr(self, "chat_mode_chip"):
            self._sync_workspace_mode_chip()
        if hasattr(self, "status_count"):
            self._update_status()
        if hasattr(self, "chat_title_label") and self.chat_title_label.text() in {"新会话", "New chat"}:
            self.chat_title_label.setText(_t("new_session"))
        self._sync_rollback_history_button_style()
        if hasattr(self, "chat_title_label") and hasattr(self, "chat_subtitle_label"):
            self._refresh_chat_header()

    def _refresh_slash_commands(self) -> None:
        if not hasattr(self, "slash_command_list") or not hasattr(self, "input"):
            return
        text = self.input.toPlainText()
        should_show = text.strip().startswith("/") and "\n" not in text
        self.slash_command_list.clear()
        if not should_show:
            self.slash_command_list.setVisible(False)
            self._sync_slash_command_layout(False)
            return
        matches = _slash_command_matches(text)
        if matches:
            for command in matches:
                item = QListWidgetItem(
                    f"{command['name']}  {command['label']} - {command['description']}"
                )
                item.setData(Qt.ItemDataRole.UserRole, command)
                item.setToolTip(str(command.get("description") or ""))
                self.slash_command_list.addItem(item)
            self.slash_command_list.setCurrentRow(0)
        else:
            item = QListWidgetItem(_t("slash_no_matches"))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.slash_command_list.addItem(item)
        self.slash_command_list.setVisible(True)
        self._sync_slash_command_layout(True)

    def _sync_slash_command_layout(self, visible: bool) -> None:
        if hasattr(self, "input_bar"):
            self.input_bar.setFixedHeight(288 if visible else 118)
        if hasattr(self, "input_wrap"):
            self.input_wrap.setMinimumHeight(252 if visible else 0)

    def _apply_slash_command_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        command = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(command, dict):
            return
        if command.get("action") == "open_model_menu":
            self.input.blockSignals(True)
            self.input.setPlainText("/model ")
            self.input.blockSignals(False)
            self._refresh_slash_commands()
            self.input.setFocus()
            cursor = self.input.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.input.setTextCursor(cursor)
            return
        if command.get("action") == "open_reasoning_menu":
            self.input.blockSignals(True)
            self.input.setPlainText("/reasoning ")
            self.input.blockSignals(False)
            self._refresh_slash_commands()
            self.input.setFocus()
            cursor = self.input.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.input.setTextCursor(cursor)
            return
        if command.get("action") == "set_model":
            model = str(command.get("model") or "").strip()
            if model:
                self._set_selected_model(model)
                self.input.clear()
                self.slash_command_list.setVisible(False)
                self._sync_slash_command_layout(False)
            return
        if command.get("action") == "set_reasoning":
            effort = str(command.get("reasoning_effort") or "").strip()
            if effort:
                self._set_selected_reasoning_effort(effort)
                self.input.clear()
                self.slash_command_list.setVisible(False)
                self._sync_slash_command_layout(False)
            return
        prompt = str(command.get("prompt") or "").strip()
        if not prompt:
            return
        self.input.blockSignals(True)
        self.input.setPlainText(prompt)
        self.input.blockSignals(False)
        self.slash_command_list.setVisible(False)
        self._sync_slash_command_layout(False)
        self.input.setFocus()
        cursor = self.input.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.input.setTextCursor(cursor)

    def _model_reasoning_label(self) -> str:
        return f"{self._selected_model} / {_reasoning_effort_label(self._selected_reasoning_effort)}"

    def _save_runtime_preferences(self) -> None:
        save_ui_preferences(
            {
                "model": self._selected_model,
                "reasoning_effort": self._selected_reasoning_effort,
            }
        )

    def _set_selected_model(self, model: str) -> None:
        self._selected_model = str(model).strip() or MODEL
        self._save_runtime_preferences()
        if hasattr(self, "chat_model_chip"):
            self.chat_model_chip.setText(self._model_reasoning_label())
        if hasattr(self, "status_model"):
            self.status_model.setText(self._model_reasoning_label())
        self._refresh_chat_header()
        self._update_status()
        if hasattr(self, "input_hint_label"):
            self.input_hint_label.setText(_tf("model_switched", model=self._selected_model))
            QTimer.singleShot(2200, lambda: self.input_hint_label.setText(_t("input_shortcut_hint")))

    def _set_selected_reasoning_effort(self, effort: str) -> None:
        self._selected_reasoning_effort = normalize_reasoning_effort(effort)
        self._save_runtime_preferences()
        if hasattr(self, "chat_model_chip"):
            self.chat_model_chip.setText(self._model_reasoning_label())
        if hasattr(self, "status_model"):
            self.status_model.setText(self._model_reasoning_label())
        self._refresh_chat_header()
        self._update_status()
        if hasattr(self, "input_hint_label"):
            label = _reasoning_effort_label(self._selected_reasoning_effort)
            self.input_hint_label.setText(_tf("reasoning_switched", effort=label))
            QTimer.singleShot(2200, lambda: self.input_hint_label.setText(_t("input_shortcut_hint")))

    def _handle_input_slash_key(self, text: str, event: QEvent) -> bool:
        if not hasattr(self, "slash_command_list") or not self.slash_command_list.isVisible():
            return False
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.slash_command_list.setVisible(False)
            self._sync_slash_command_layout(False)
            return True
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            count = self.slash_command_list.count()
            if count <= 0:
                return True
            current = self.slash_command_list.currentRow()
            delta = -1 if key == Qt.Key.Key_Up else 1
            self.slash_command_list.setCurrentRow(max(0, min(count - 1, current + delta)))
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self._apply_slash_command_item(self.slash_command_list.currentItem())
            return True
        return False

    def _sync_workspace_mode_chip(self) -> None:
        if not hasattr(self, "chat_mode_chip"):
            return
        if self._current_workspace_root():
            self.chat_mode_chip.setText(_t("project_chat_mode"))
            self.chat_mode_chip.setStyleSheet(
                "background: rgba(20, 184, 166, 0.12); color: #CCFBF1; "
                "border: 1px solid rgba(20, 184, 166, 0.30); border-radius: 999px; "
                "padding: 4px 10px; font-size: 11px; font-weight: 700;"
            )
        else:
            self.chat_mode_chip.setText(_t("no_project_chat_mode"))
            self.chat_mode_chip.setStyleSheet(
                "background: rgba(148, 163, 184, 0.10); color: #CBD5E1; "
                "border: 1px solid rgba(148, 163, 184, 0.24); border-radius: 999px; "
                "padding: 4px 10px; font-size: 11px; font-weight: 700;"
            )

    def _scope_label(self, value: str) -> str:
        return _t("all_scope") if str(value).strip().lower() == "all" else _t("workspace_scope")

    def _scope_action(
        self,
        menu: QMenu,
        label: str,
        env_key: str,
        current: str,
    ) -> None:
        submenu = menu.addMenu(f"{label}: {self._scope_label(current)}")
        submenu.setStyleSheet(_menu_style())
        for value, value_label in (("workspace", _t("workspace_scope")), ("all", _t("all_scope"))):
            action = QAction(value_label, submenu)
            action.setCheckable(True)
            action.setChecked(str(current).strip().lower() == value)
            action.triggered.connect(
                lambda checked=False, key=env_key, selected=value: self._set_permission_scope(key, selected)
            )
            submenu.addAction(action)

    def _show_permission_menu(self) -> None:
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("settings_busy"))
            return

        menu = QMenu(self)
        menu.setStyleSheet(_menu_style())
        self._scope_action(menu, _t("read_permission"), "KAGENT_FS_READ_SCOPE", app_config.FILESYSTEM_READ_SCOPE)
        self._scope_action(menu, _t("write_permission"), "KAGENT_FS_WRITE_SCOPE", app_config.FILESYSTEM_WRITE_SCOPE)
        self._scope_action(menu, _t("command_permission"), "KAGENT_FS_COMMAND_SCOPE", app_config.FILESYSTEM_COMMAND_SCOPE)
        menu.addSeparator()
        settings_action = QAction(_t("settings_heading"), menu)
        settings_action.triggered.connect(self._open_permission_settings)
        menu.addAction(settings_action)
        menu.exec(self.permission_menu_btn.mapToGlobal(self.permission_menu_btn.rect().bottomLeft()))

    def _show_workspace_menu(self) -> None:
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return

        menu = QMenu(self)
        menu.setStyleSheet(_menu_style())
        recent = _recent_workspace_roots(db.list_sessions())
        if recent:
            recent_menu = menu.addMenu(_t("recent_workspaces"))
            recent_menu.setStyleSheet(_menu_style())
            for root in recent:
                action = QAction(Path(root).name or root, recent_menu)
                action.setToolTip(root)
                action.triggered.connect(lambda checked=False, selected=root: self._set_current_workspace_root(selected))
                recent_menu.addAction(action)
            menu.addSeparator()
        select_action = QAction(_t("select_workspace"), menu)
        select_action.triggered.connect(self._choose_workspace_for_session)
        menu.addAction(select_action)

        clear_action = QAction(_t("clear_workspace"), menu)
        clear_action.triggered.connect(self._clear_workspace_for_session)
        menu.addAction(clear_action)

        menu.exec(self.workspace_btn.mapToGlobal(self.workspace_btn.rect().bottomLeft()))

    def _command_palette_actions(self) -> list[dict[str, str]]:
        return [
            {"label": _t("command_new_chat"), "action": "new_chat", "keywords": "new chat session"},
            {"label": _t("command_new_project_chat"), "action": "new_project_chat", "keywords": "folder workspace project"},
            {"label": _t("command_switch_workspace"), "action": "switch_workspace", "keywords": "project workspace folder"},
            {"label": _t("command_no_folder"), "action": "no_folder", "keywords": "plain chat no project"},
            {"label": _t("command_diff_review"), "action": "diff_review", "keywords": "diff review changes"},
            {"label": _t("command_toggle_history"), "action": "toggle_history", "keywords": "rollback history"},
            {"label": _t("command_permissions"), "action": "permissions", "keywords": "settings language scope"},
            {"label": _t("command_resume_latest"), "action": "resume_latest", "keywords": "resume task run log"},
        ]

    def _open_command_palette(self) -> None:
        dialog = CommandPaletteDialog(self._command_palette_actions(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_action:
            return
        self._execute_palette_action(dialog.selected_action)

    def _execute_palette_action(self, action: str) -> None:
        if action == "new_chat":
            self.new_session()
        elif action == "new_project_chat":
            self.new_session_from_folder()
        elif action == "switch_workspace":
            self._choose_workspace_for_session()
        elif action == "no_folder":
            self._clear_workspace_for_session()
        elif action == "diff_review":
            self._show_current_diff_review()
        elif action == "toggle_history":
            self._toggle_rollback_history_panel(not self._rollback_history_visible)
        elif action == "permissions":
            self._show_permission_menu()
        elif action == "resume_latest":
            self._resume_latest_task()

    def _resume_latest_task(self) -> None:
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return
        try:
            context = build_latest_resume_context()
        except Exception as exc:
            QMessageBox.warning(self, "kagent", _tf("build_resume_context_failed", error=exc))
            return
        if not context:
            QMessageBox.information(self, "kagent", _t("no_run_log_path"))
            return
        self._submit_text(_resume_task_prompt(context), clear_input=False)

    def _choose_workspace_for_session(self) -> None:
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return
        current = self._current_workspace_root() or str(Path(app_config.WORKSPACE_ROOT).expanduser().resolve())
        selected = QFileDialog.getExistingDirectory(
            self,
            _t("select_workspace"),
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return
        self._set_current_workspace_root(selected)

    def _clear_workspace_for_session(self) -> None:
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return
        if not self.current_session:
            self.new_session()
        if not self.current_session:
            return
        db.set_session_workspace_root(self.current_session, "")
        self._load_sessions()
        self._refresh_chat_header()
        self._refresh_rollback_history_panel()

    def _set_permission_scope(self, key: str, value: str) -> None:
        self._apply_settings_values({key: value})
        self._apply_language_texts()
        self._refresh_chat_header()

    def _open_permission_settings(self) -> None:
        if self._is_busy():
            QMessageBox.information(
                self,
                "kagent",
                _t("settings_busy"),
            )
            return

        dialog = PermissionSettingsDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        self._apply_settings_values(values)
        self._apply_language_texts()
        self._refresh_chat_header()
        QMessageBox.information(self, "kagent", _t("settings_saved"))

    def _apply_settings_values(self, values: dict[str, str]) -> None:
        env_path = Path(app_config.BASE_DIR) / ".env"
        env_path.touch(exist_ok=True)

        for key, value in values.items():
            normalized = str(value or "").strip()
            os.environ[key] = normalized
            set_key(str(env_path), key, normalized)

        if "APP_LANGUAGE" in values:
            app_config.APP_LANGUAGE = _language_code(values.get("APP_LANGUAGE"))
        if "KAGENT_FS_READ_SCOPE" in values:
            app_config.FILESYSTEM_READ_SCOPE = values["KAGENT_FS_READ_SCOPE"]
        if "KAGENT_FS_WRITE_SCOPE" in values:
            app_config.FILESYSTEM_WRITE_SCOPE = values["KAGENT_FS_WRITE_SCOPE"]
        if "KAGENT_FS_COMMAND_SCOPE" in values:
            app_config.FILESYSTEM_COMMAND_SCOPE = values["KAGENT_FS_COMMAND_SCOPE"]
        if "KAGENT_ALLOWED_WRITE_ROOTS" in values:
            app_config.ALLOWED_WRITE_ROOTS = values["KAGENT_ALLOWED_WRITE_ROOTS"]
        if "KAGENT_ALLOWED_COMMAND_ROOTS" in values:
            app_config.ALLOWED_COMMAND_ROOTS = values["KAGENT_ALLOWED_COMMAND_ROOTS"]

        from ..agent import code_agent as code_agent_module
        from ..agent import workspace as workspace_module

        workspace_module.FILESYSTEM_READ_SCOPE = app_config.FILESYSTEM_READ_SCOPE
        workspace_module.FILESYSTEM_WRITE_SCOPE = app_config.FILESYSTEM_WRITE_SCOPE
        workspace_module.FILESYSTEM_COMMAND_SCOPE = app_config.FILESYSTEM_COMMAND_SCOPE
        workspace_module.ALLOWED_WRITE_ROOTS = app_config.ALLOWED_WRITE_ROOTS
        workspace_module.ALLOWED_COMMAND_ROOTS = app_config.ALLOWED_COMMAND_ROOTS
        code_agent_module.FILESYSTEM_READ_SCOPE = app_config.FILESYSTEM_READ_SCOPE
        code_agent_module.FILESYSTEM_WRITE_SCOPE = app_config.FILESYSTEM_WRITE_SCOPE
        code_agent_module.FILESYSTEM_COMMAND_SCOPE = app_config.FILESYSTEM_COMMAND_SCOPE
        code_agent_module.APP_LANGUAGE = app_config.APP_LANGUAGE

    def _workspace_tools_for_session(self) -> WorkspaceTools | None:
        if not self.current_session:
            return None
        if not self._current_workspace_root():
            return None
        return WorkspaceTools(
            root=self._current_workspace_root(),
            session_id=self.current_session,
        )

    def _current_workspace_root(self) -> str:
        if self.current_session:
            session = db.get_session(self.current_session)
            if session is not None:
                return str(session.get("workspace_root") or "")
        return str(Path(app_config.WORKSPACE_ROOT).expanduser().resolve())

    def _workspace_header_label(self) -> str:
        root = self._current_workspace_root()
        if not root:
            return f"{_t('no_project_chat_mode')} | {_t('no_project_chat_detail')}"
        return _tf("workspace_label", path=root)

    def _set_current_workspace_root(self, workspace_root: str) -> None:
        if not self.current_session:
            self.new_session()
        if not self.current_session:
            return
        root = Path(workspace_root).expanduser()
        if not root.exists() or not root.is_dir():
            QMessageBox.warning(self, "kagent", _tf("workspace_missing", path=str(root)))
            return
        db.set_session_workspace_root(self.current_session, str(root.resolve()))
        self._load_sessions()
        self._refresh_chat_header()
        self._refresh_rollback_history_panel()

    def _set_rollback_detail_empty(self, text: str | None = None) -> None:
        if not hasattr(self, "rollback_detail_title"):
            return
        self.rollback_detail_title.setText(text or _t("rollback_select"))
        self.rollback_detail_meta.setText(_t("rollback_meta_empty"))
        self.rollback_detail_files.setText("")
        self.rollback_detail_body.setHtml(
            f'<div class="typing">{html.escape(_t("rollback_preview_empty"))}</div>'
        )
        self.rollback_open_trace_btn.setEnabled(False)
        self.rollback_restore_btn.setEnabled(False)

    def _toggle_rollback_history_panel(self, checked: bool | None = None) -> None:
        visible = self._rollback_history_visible if checked is None else bool(checked)
        self._rollback_history_visible = visible
        if hasattr(self, "rollback_panel"):
            self.rollback_panel.setVisible(visible)
        if hasattr(self, "rollback_history_btn") and self.rollback_history_btn.isChecked() != visible:
            self.rollback_history_btn.blockSignals(True)
            self.rollback_history_btn.setChecked(visible)
            self.rollback_history_btn.blockSignals(False)
        self._sync_rollback_history_button_style()
        if visible:
            self._refresh_rollback_history_panel()

    def _format_rollback_list_item(self, item: dict[str, Any]) -> str:
        rollback_id = item.get("rollback_id")
        status = str(item.get("status") or "").strip() or "unknown"
        source_tool = str(item.get("source_tool") or "").strip() or "tool"
        summary = str(item.get("summary") or "").strip()
        paths = item.get("paths") if isinstance(item.get("paths"), list) else []
        path_label = ", ".join(str(path) for path in paths[:2]) if paths else _t("no_file_details")
        if len(paths) > 2:
            path_label += f" (+{len(paths) - 2})"
        symbol_label = _symbol_impacts_inline(item.get("symbol_impacts"))
        if symbol_label:
            path_label += f"\nSymbols: {symbol_label}"
        return (
            f"#{rollback_id}  {source_tool}  [{status}]\n"
            f"{summary}\n"
            f"{path_label}"
        )

    def _format_session_list_item(self, session: dict[str, Any]) -> str:
        title = str(session.get("title") or _t("new_session"))
        current = session.get("id") == self.current_session
        summary = _session_workspace_summary(session, current=current)
        marker = "● " if current else "  "
        return f"{marker}{title}\n   {summary}"

    def _refresh_rollback_history_panel(self, select_id: int | None = None) -> None:
        if not hasattr(self, "rollback_list"):
            return

        workspace = self._workspace_tools_for_session()
        if workspace is None:
            self.rollback_list.clear()
            self.rollback_count_label.setText(f"0 {_t('entries')}")
            self._rollback_history_items = []
            self._selected_rollback_id = None
            self._set_rollback_detail_empty(
                _t("no_active_session") if not self.current_session else _t("no_project_for_workspace_action")
            )
            return

        data = workspace.list_rollback_history(limit=40, include_inactive=True)
        entries = data.get("entries") if isinstance(data.get("entries"), list) else []
        self._rollback_history_items = [item for item in entries if isinstance(item, dict)]
        self.rollback_count_label.setText(f"{len(self._rollback_history_items)} {_t('entries')}")

        current_id = select_id if select_id is not None else self._selected_rollback_id
        self.rollback_list.blockSignals(True)
        self.rollback_list.clear()
        selected_row = -1
        for idx, item in enumerate(self._rollback_history_items):
            list_item = QListWidgetItem(self._format_rollback_list_item(item))
            list_item.setData(Qt.ItemDataRole.UserRole, int(item["rollback_id"]))
            list_item.setToolTip(self._format_rollback_list_item(item))
            list_item.setSizeHint(QSize(0, 82 if item.get("symbol_impacts") else 66))
            self.rollback_list.addItem(list_item)
            if current_id is not None and int(item["rollback_id"]) == int(current_id):
                selected_row = idx
        if selected_row == -1 and self._rollback_history_items:
            selected_row = 0
        if selected_row >= 0:
            self.rollback_list.setCurrentRow(selected_row)
        self.rollback_list.blockSignals(False)

        if selected_row >= 0:
            item = self.rollback_list.item(selected_row)
            if item is not None:
                self._show_rollback_detail(int(item.data(Qt.ItemDataRole.UserRole)))
        else:
            self._selected_rollback_id = None
            self._set_rollback_detail_empty(_t("no_rollback_history"))

    def _on_rollback_item_selection_changed(self) -> None:
        if not hasattr(self, "rollback_list"):
            return
        item = self.rollback_list.currentItem()
        if item is None:
            self._selected_rollback_id = None
            self._set_rollback_detail_empty()
            return
        rollback_id = item.data(Qt.ItemDataRole.UserRole)
        if rollback_id is None:
            return
        self._show_rollback_detail(int(rollback_id))


    def _show_rollback_detail(self, rollback_id: int) -> None:
        workspace = self._workspace_tools_for_session()
        if workspace is None:
            self._set_rollback_detail_empty(_t("no_active_session"))
            return

        preview = workspace.preview_rollback_change(int(rollback_id))
        self._selected_rollback_id = int(rollback_id)
        status = str(preview.get("status") or "unknown").strip() or "unknown"
        source_tool = str(preview.get("source_tool") or "rollback").strip() or "rollback"

        self.rollback_detail_title.setText(f"#{rollback_id} | {source_tool}")
        self.rollback_detail_meta.setText(
            _tf(
                "rollback_status_meta",
                status=status,
                files=int(preview.get("path_count") or 0),
                created=preview.get("created_at") or "-",
            )
        )

        diff_entries = preview.get("diff_entries") if isinstance(preview.get("diff_entries"), list) else []
        file_lines = []
        for entry in diff_entries:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip() or f"({_t('unknown_path')})"
            action = _rollback_change_type_label(str(entry.get("action") or ""))
            symbol_label = _symbol_impacts_inline(entry.get("symbol_impacts"))
            suffix = f" | symbols: {symbol_label}" if symbol_label else ""
            file_lines.append(f"- {path} | {action}{suffix}")
        self.rollback_detail_files.setText(
            "\n".join(file_lines) if file_lines else _t("no_file_details")
        )

        md = [
            f"### {_tf('rollback_title', rollback_id=rollback_id)}",
            "",
            f"**{_t('status')}**: {status}",
            "",
            f"**{_t('summary')}**: {preview.get('summary') or '-'}",
            "",
            *(
                ["**Symbol impacts**", "", *_symbol_impacts_markdown_lines(preview.get("symbol_impacts")), ""]
                if _symbol_impacts_markdown_lines(preview.get("symbol_impacts"))
                else []
            ),
            _preview_markdown_block(str(preview.get("preview") or "")),
        ]
        self.rollback_detail_body.setHtml(render("\n".join(md)))

        available = bool(preview.get("available", False))
        self.rollback_open_trace_btn.setEnabled(preview.get("rollback_id") is not None)
        self.rollback_restore_btn.setEnabled(available)

    def _open_selected_rollback_preview_in_chat(self) -> None:
        rollback_id = self._selected_rollback_id
        if rollback_id is None:
            return
        prompt = (
            _tf("rollback_preview_prompt", rollback_id=int(rollback_id))
        )
        self._submit_text(prompt, clear_input=False)

    def _restore_selected_rollback(self) -> None:
        rollback_id = self._selected_rollback_id
        if rollback_id is None:
            return
        prompt = (
            _tf("rollback_restore_prompt", rollback_id=int(rollback_id))
        )
        self._submit_text(prompt, clear_input=False)

    def _build_empty_state(self) -> QFrame:
        card = QFrame()
        card.setFixedWidth(430)
        card.setStyleSheet(
            "background: rgba(13, 22, 36, 0.78); "
            f"border: 1px solid {C_BORDER}; border-radius: 22px;"
        )

        v = QVBoxLayout(card)
        v.setContentsMargins(26, 24, 26, 22)
        v.setSpacing(10)

        badge = QLabel("K")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}); "
            "color: #03111A; border-radius: 14px; font-size: 20px; font-weight: 800;"
        )
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        v.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("kagent")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 24px; font-weight: 800;")
        v.addWidget(title)

        prompts = QVBoxLayout()
        prompts.setSpacing(8)
        quick_prompts = _project_quick_prompts(self._current_workspace_root())
        if not quick_prompts:
            quick_prompts = [
                {"label": _t("prompt_check_project"), "prompt": _t("prompt_check_project_text")},
                {"label": _t("prompt_fix_tests"), "prompt": _t("prompt_fix_tests_text")},
                {"label": _t("prompt_explain_project"), "prompt": _t("prompt_explain_project_text")},
            ]
        for item in quick_prompts[:3]:
            label = str(item.get("label") or "")
            prompt = str(item.get("prompt") or "")
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                "background: rgba(255, 255, 255, 0.026);"
                "color: #DDE7F3;"
                f"border: 1px solid {C_BORDER};"
                "border-radius: 12px;"
                "padding: 9px 12px;"
                "font-size: 12px;"
                "font-weight: 700;"
                "text-align: left;"
                "}"
                "QPushButton:hover {"
                "background: rgba(56, 189, 248, 0.09);"
                "border: 1px solid rgba(56, 189, 248, 0.26);"
                "}"
            )
            btn.clicked.connect(lambda checked=False, text=prompt: self._submit_text(text, clear_input=False))
            prompts.addWidget(btn)
        v.addLayout(prompts)

        hint = QLabel(_t("input_shortcut_hint"))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 12px;")
        v.addWidget(hint)

        return card

    def _scroll_to_bottom(self):
        scrollbar = self.chat_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self._update_scroll_to_bottom_button()

    def _update_scroll_to_bottom_button(self, *args):
        btn = getattr(self, "scroll_bottom_btn", None)
        if btn is None:
            return

        scrollbar = self.chat_scroll.verticalScrollBar()
        maximum = scrollbar.maximum()
        value = scrollbar.value()
        should_show = maximum > 0 and value < max(0, maximum - 4)

        if should_show:
            viewport = self.chat_scroll.viewport()
            margin = 18
            x = max(margin, viewport.width() - btn.width() - margin)
            y = max(margin, viewport.height() - btn.height() - margin)
            btn.move(x, y)
            btn.show()
            btn.raise_()
        else:
            btn.hide()

    def eventFilter(self, obj, event):
        viewport = self.chat_scroll.viewport() if hasattr(self, "chat_scroll") else None
        if obj is viewport and event.type() == QEvent.Type.Resize:
            self._update_scroll_to_bottom_button()
        return super().eventFilter(obj, event)

    # ==================== Sessions ====================

    def _load_sessions(self):
        self.session_list.blockSignals(True)
        self.session_list.clear()
        sessions = db.list_sessions()
        for s in sessions:
            title = s["title"] or _t("new_session")
            item = QListWidgetItem(self._format_session_list_item(s))
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            item.setToolTip(str(s.get("workspace_root") or _t("no_project_chat_detail")))
            item.setSizeHint(QSize(0, 62))
            self.session_list.addItem(item)
            if s["id"] == self.current_session:
                self.session_list.setCurrentItem(item)
        self.session_list.blockSignals(False)
        self._update_status()

    def _current_session_title(self) -> str:
        if self.current_session:
            for s in db.list_sessions():
                if s["id"] == self.current_session:
                    return s["title"] or _t("new_session")
        item = self.session_list.currentItem()
        if item is not None:
            return (item.text().splitlines() or [_t("new_session")])[0] or _t("new_session")
        return _t("new_session")

    def _open_session(self, session_id: str):
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return

        self.current_session = session_id
        self._streaming_buf = ""
        self._streaming_time = ""
        self._activity = "Ready"
        self._send_locked = False
        self._reset_tool_trace()
        self._load_sessions()
        msgs = db.get_messages(session_id)
        self._render_messages(msgs)
        self._refresh_rollback_history_panel()
        self.input.setFocus()

    def new_session(self):
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return

        sid = uuid.uuid4().hex[:12]
        db.create_session(sid, workspace_root=self._current_workspace_root())
        self._open_session(sid)

    def new_session_from_folder(self):
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return

        selected = QFileDialog.getExistingDirectory(
            self,
            _t("select_workspace_for_new_chat"),
            self._current_workspace_root() or str(Path(app_config.WORKSPACE_ROOT).expanduser().resolve()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return

        root = Path(selected).expanduser()
        if not root.exists() or not root.is_dir():
            QMessageBox.warning(self, "kagent", _tf("workspace_missing", path=str(root)))
            return

        sid = uuid.uuid4().hex[:12]
        title = _session_title_for_workspace(root)
        db.create_session(sid, title=title, workspace_root=str(root.resolve()))
        self._open_session(sid)

    def _delete_current_session(self):
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_delete_session"))
            return
        if not self.current_session:
            return

        title = self._current_session_title()
        answer = QMessageBox.question(
            self,
            _t("delete_session_title"),
            _tf("delete_session_confirm", title=title),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        db.delete_session(self.current_session)
        remaining = db.list_sessions()
        if remaining:
            self.current_session = remaining[0]["id"]
            self._open_session(self.current_session)
        else:
            self.current_session = None
            self._streaming_buf = ""
            self._streaming_time = ""
            self._activity = "Ready"
            self._reset_tool_trace()
            self._load_sessions()
            self._render_messages([])
            self._refresh_rollback_history_panel()
            self.input.setFocus()

    def _on_session_clicked(self, item: QListWidgetItem):
        sid = item.data(Qt.ItemDataRole.UserRole)
        self._open_session(sid)

    # ==================== Render ====================

    def _clear_feed(self):
        _clear_layout(self.chat_layout)
        self._agent_trace_card = None
        self._agent_trace_row = None

    def _bubble_width(self, role: str, content: str) -> int:
        viewport_width = self.chat_scroll.viewport().width()
        return _body_width_for_card(viewport_width, role, content)

    def _build_message_row(
        self,
        role: str,
        content: str,
        created_at: str | None = None,
        streaming: bool = False,
        thinking: bool = False,
        error: bool = False,
    ) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        card_width = self._bubble_width(role, content)
        card = MessageCard(
            role=role,
            content=content,
            created_at=created_at,
            width=card_width,
            streaming=streaming,
            thinking=thinking,
            error=error,
        )

        if role == "assistant":
            avatar = _avatar_label("K", C_ACCENT)
            row_layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
            row_layout.addStretch(1)
            if streaming or thinking:
                self._streaming_card = card
                self._streaming_row = row
        else:
            avatar = _avatar_label("U", C_USER_ACCENT)
            row_layout.addStretch(1)
            row_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)

        return row

    def _ensure_agent_trace_card(self) -> ToolTraceCard | None:
        if self._agent_trace_card is not None:
            return self._agent_trace_card

        width = self._bubble_width("assistant", "")
        trace = ToolTraceCard(width)
        trace.approval_decided.connect(self._resolve_inline_approval)
        trace.action_requested.connect(self._handle_trace_action)
        trace.set_state(_t("tool_status_running"), kind="active")

        insert_at = -1
        if self._streaming_row is not None:
            insert_at = self.chat_layout.indexOf(self._streaming_row)
        if insert_at >= 0:
            self.chat_layout.insertWidget(insert_at, trace)
        else:
            self.chat_layout.addWidget(trace)

        self._agent_trace_card = trace
        self._agent_trace_row = trace
        if self._tool_trace_events:
            for event in self._tool_trace_events:
                self._apply_tool_event(trace, event)
        return trace

    def _reset_tool_trace(self):
        self._tool_trace_events = []
        self._agent_trace_card = None
        self._agent_trace_row = None

    def _apply_tool_event(self, trace: ToolTraceCard, event: dict[str, Any]):
        event_type = str(event.get("type", "")).strip()
        if event_type == "agent_start":
            trace.set_run_info(
                run_id=str(event.get("run_id") or ""),
                run_log_path=str(event.get("run_log_path") or ""),
            )
            trace.set_state(_t("analyzing"), kind="active")
            return
        if event_type == "final_trust_check":
            trust = event.get("trust") if isinstance(event.get("trust"), dict) else {}
            trace.set_trust_summary(trust)
            health = str(trust.get("health") or "").strip()
            if health == "fail":
                trace.set_state(_t("trust_attention"), kind="error")
            elif health == "warn":
                trace.set_state(_t("trust_risky"), kind="active")
            elif health == "pass":
                trace.set_state(_t("trustworthy"), kind="done")
            return
        if event_type == "agent_plan":
            plan = event.get("plan") if isinstance(event.get("plan"), list) else []
            trace.set_plan([item for item in plan if isinstance(item, dict)])
            return
        if event_type == "agent_status":
            status_text = str(event.get("status") or "").strip()
            if status_text:
                trace.set_state(status_text, kind=str(event.get("kind") or "active"))
            return
        if event_type == "project_rules_check":
            health = str(event.get("health") or "").strip()
            issue_count = event.get("issue_count")
            error = health in {"missing", "weak"} or (
                isinstance(issue_count, int) and issue_count > 0
            )
            trace.upsert_event(
                call_id="project_rules_check",
                name="KAGENT.md rules",
                status=_t("tool_status_failed") if error else _t("tool_status_success"),
                result={
                    "path": event.get("path") or "KAGENT.md",
                    "health": health or "unknown",
                    "score": event.get("score"),
                    "issue_count": issue_count,
                    "issues": event.get("issues") if isinstance(event.get("issues"), list) else [],
                },
                error=error,
                approval_pending=False,
            )
            return
        call_id = str(event.get("call_id") or event.get("id") or "")
        if not call_id:
            return

        name = str(event.get("name") or "tool")
        round_idx = event.get("round")
        try:
            round_idx = int(round_idx) if round_idx is not None else None
        except (TypeError, ValueError):
            round_idx = None
        policy = event.get("policy") if isinstance(event.get("policy"), dict) else None

        if event_type == "tool_preview":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            preview = str(event.get("preview") or "")
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status=_t("tool_status_preview"),
                args=args,
                preview=preview,
                round_idx=round_idx,
                approval_pending=False,
                policy=policy,
            )
        elif event_type == "tool_start":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status=_t("tool_status_running"),
                args=args,
                round_idx=round_idx,
                approval_pending=False,
                policy=policy,
            )
        elif event_type == "tool_approval_required":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            preview = str(event.get("preview") or "")
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status=_t("tool_status_preview"),
                args=args,
                preview=preview,
                round_idx=round_idx,
                approval_pending=True,
                policy=policy,
            )
            trace.set_state(_t("waiting_confirmation"), kind="active")
        elif event_type == "tool_approval_decision":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            preview = str(event.get("preview") or "")
            approved = bool(event.get("approved", False))
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status=_t("tool_status_running") if approved else _t("tool_status_failed"),
                args=args,
                preview=preview,
                round_idx=round_idx,
                error=not approved,
                approval_pending=False,
                policy=policy,
            )
            trace.set_state(
                _t("tool_status_running") if approved else _t("tool_status_failed"),
                kind="active" if approved else "error",
            )
        elif event_type == "tool_result":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            result = event.get("result") if isinstance(event.get("result"), dict) else {}
            error = not bool(event.get("ok", True))
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status=_t("tool_status_failed") if error else _t("tool_status_success"),
                args=args,
                result=result,
                round_idx=round_idx,
                error=error,
                approval_pending=False,
                policy=policy,
            )
            if error:
                trace.set_state(_t("tool_status_failed"), kind="error")

    def _render_messages(
        self,
        msgs: list[dict],
        streaming_html: str | None = None,
        thinking: bool = False,
        error_text: str | None = None,
    ):
        scrollbar = self.chat_scroll.verticalScrollBar()
        prev_value = scrollbar.value()
        prev_max = scrollbar.maximum()
        stick_to_bottom = prev_value >= max(0, prev_max - 4)
        has_content = bool(msgs) or streaming_html is not None or thinking or error_text is not None

        self._render_seq += 1
        render_seq = self._render_seq

        self.chat_scroll.setUpdatesEnabled(False)
        self.chat_scroll.viewport().setUpdatesEnabled(False)
        self.chat_content.setUpdatesEnabled(False)
        self._streaming_card = None
        self._streaming_row = None

        try:
            self._clear_feed()

            if not msgs and streaming_html is None and not thinking and error_text is None:
                self.chat_layout.addStretch(1)
                empty = self._build_empty_state()
                self.chat_layout.addWidget(empty, 0, Qt.AlignmentFlag.AlignHCenter)
                self.chat_layout.addStretch(1)
            else:
                for m in msgs:
                    row = self._build_message_row(
                        m["role"],
                        m["content"],
                        created_at=m.get("created_at"),
                    )
                    self.chat_layout.addWidget(row)

                if (
                    self._tool_trace_events
                    or streaming_html is not None
                    or thinking
                    or error_text is not None
                ):
                    self._ensure_agent_trace_card()

                if streaming_html is not None or thinking:
                    row = self._build_message_row(
                        "assistant",
                        streaming_html or "",
                        created_at=self._streaming_time,
                        streaming=streaming_html is not None,
                        thinking=thinking,
                    )
                    self.chat_layout.addWidget(row)

                if error_text is not None:
                    row = self._build_message_row(
                        "assistant",
                        error_text,
                        created_at=self._streaming_time,
                        error=True,
                    )
                    self.chat_layout.addWidget(row)

                self.chat_layout.addStretch(1)
        finally:
            QTimer.singleShot(
                0,
                lambda seq=render_seq,
                value=prev_value,
                stick=stick_to_bottom,
                content=has_content,
                stream_html=streaming_html,
                is_thinking=thinking,
                is_error=error_text is not None: self._finish_render(
                    seq,
                    value,
                    stick,
                    content,
                    stream_html,
                    is_thinking,
                    is_error,
                ),
            )

    def _finish_render(
        self,
        render_seq: int,
        prev_value: int,
        stick_to_bottom: bool,
        has_content: bool,
        streaming_html: str | None,
        thinking: bool,
        is_error: bool,
    ) -> None:
        if render_seq != self._render_seq:
            return

        scrollbar = self.chat_scroll.verticalScrollBar()
        self.chat_layout.activate()
        self.chat_content.adjustSize()

        if has_content:
            target = scrollbar.maximum()
            if not (streaming_html is not None or thinking or is_error or stick_to_bottom):
                target = min(prev_value, scrollbar.maximum())
            scrollbar.setValue(target)

        self._refresh_chat_header()
        self._update_status()
        self.chat_content.setUpdatesEnabled(True)
        self.chat_scroll.viewport().setUpdatesEnabled(True)
        self.chat_scroll.setUpdatesEnabled(True)
        self.chat_scroll.viewport().update()
        self._update_scroll_to_bottom_button()

    def _resolve_inline_approval(self, call_id: str, approved: bool) -> None:
        worker = self.worker
        if worker is None or not call_id:
            return
        worker.resolve_approval(call_id, approved)

    def _handle_trace_action(self, action: object) -> None:
        payload = action if isinstance(action, dict) else {}
        action_name = str(payload.get("action") or "").strip()
        if action_name == "show_run_debug":
            self._show_run_debug(payload)
            return
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return
        self._submit_text(prompt, clear_input=False)

    def _show_run_debug(self, payload: dict[str, Any]) -> None:
        run_log_path = str(payload.get("run_log_path") or "").strip()
        mode = str(payload.get("mode") or "summary").strip()
        if not run_log_path:
            QMessageBox.information(self, "kagent", _t("no_run_log_path"))
            return
        try:
            markdown = _run_debug_markdown(run_log_path, mode)
        except Exception as exc:
            QMessageBox.warning(self, "kagent", _tf("read_run_log_failed", error=exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(_t("run_debug_title"))
        dialog.resize(760, 620)
        dialog.setStyleSheet(_dialog_style())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(_tf("run_log_label", name=Path(run_log_path).name))
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 14px; font-weight: 800;")
        layout.addWidget(title)

        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setStyleSheet(
            f"background: {C_BG_SURFACE}; color: {C_TEXT_MAIN}; "
            f"border: 1px solid {C_BORDER}; border-radius: 14px; padding: 10px;"
        )
        view.setHtml(render(markdown))
        layout.addWidget(view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        resume_button = buttons.addButton(
            _t("resume_task"), QDialogButtonBox.ButtonRole.ActionRole
        )
        resume_button.clicked.connect(
            lambda _checked=False, path=run_log_path, dlg=dialog: self._resume_run_from_debug(
                path, dlg
            )
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _resume_run_from_debug(self, run_log_path: str, dialog: QDialog | None = None) -> None:
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return
        try:
            context = build_resume_context(run_log_path)
            prompt = _resume_task_prompt(context)
        except Exception as exc:
            QMessageBox.warning(self, "kagent", _tf("build_resume_context_failed", error=exc))
            return
        if dialog is not None:
            dialog.accept()
        self._submit_text(prompt, clear_input=False)

    def _resume_diff_preview_for_row(
        self, row: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any] | None:
        session_id = str(row.get("session_id") or self.current_session or "").strip()
        workspace_root = str(row.get("workspace_root") or self._current_workspace_root() or "").strip()
        if not session_id or not workspace_root:
            return None
        try:
            workspace = WorkspaceTools(root=workspace_root, session_id=session_id)
            changed_paths = [
                str(path)
                for path in context.get("changed_paths", [])
                if str(path).strip()
            ]
            if changed_paths:
                preview = workspace.preview_rollback_paths(changed_paths)
                if preview.get("available") or preview.get("paths"):
                    return preview
            preview = workspace.preview_rollback_session(limit=80)
            return preview if preview.get("available") or preview.get("paths") else None
        except Exception:
            return None

    def _show_resume_history_picker(self) -> None:
        if self._is_busy():
            QMessageBox.information(self, "kagent", _t("busy_action_message"))
            return
        try:
            rows = list_run_history(limit=80)
            candidates = _resume_history_candidates(
                rows,
                workspace_root=self._current_workspace_root(),
                limit=30,
            )
        except Exception as exc:
            QMessageBox.warning(self, "kagent", _tf("build_resume_context_failed", error=exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(_t("resume_history_title"))
        dialog.resize(980, 660)
        dialog.setStyleSheet(f"background: {C_BG_PANEL}; color: {C_TEXT_MAIN};")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(_t("resume_history_title"))
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-weight: 800;")
        layout.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(10)

        run_list = QListWidget()
        run_list.setStyleSheet(
            f"background: {C_BG_SURFACE}; color: {C_TEXT_MAIN}; "
            f"border: 1px solid {C_BORDER}; border-radius: 14px; padding: 6px;"
        )
        body.addWidget(run_list, 1)

        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setStyleSheet(
            f"background: {C_BG_SURFACE}; color: {C_TEXT_MAIN}; "
            f"border: 1px solid {C_BORDER}; border-radius: 14px; padding: 10px;"
        )
        preview_stack = QVBoxLayout()
        preview_stack.setSpacing(8)
        preview_stack.addWidget(view, 2)

        prompt_label = QLabel(_t("resume_prompt_editor"))
        prompt_label.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 11px; font-weight: 700;")
        preview_stack.addWidget(prompt_label)

        prompt_editor = QTextEdit()
        prompt_editor.setStyleSheet(_text_view_style())
        prompt_editor.setMinimumHeight(120)
        prompt_editor.setAcceptRichText(False)
        preview_stack.addWidget(prompt_editor, 1)

        body.addLayout(preview_stack, 2)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        back_activity_button = buttons.addButton(
            _t("activity_back_to_activity"), QDialogButtonBox.ButtonRole.ActionRole
        )
        copy_button = buttons.addButton(
            _t("copy_resume_prompt"), QDialogButtonBox.ButtonRole.ActionRole
        )
        resume_button = buttons.addButton(
            _t("resume_selected"), QDialogButtonBox.ButtonRole.ActionRole
        )
        copy_button.setEnabled(False)
        resume_button.setEnabled(False)
        buttons.rejected.connect(dialog.reject)
        back_activity_button.clicked.connect(
            lambda _checked=False, dlg=dialog: self._return_dialog_to_activity(dlg)
        )
        layout.addWidget(buttons)

        contexts: dict[str, dict[str, Any]] = {}
        rows_by_path = {str(row.get("path") or ""): row for row in candidates}

        def show_selected(item: QListWidgetItem | None) -> None:
            if item is None:
                resume_button.setEnabled(False)
                return
            path = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if not path:
                resume_button.setEnabled(False)
                return
            try:
                context = contexts.get(path)
                if context is None:
                    context = build_resume_context(path)
                    contexts[path] = context
                diff_preview = self._resume_diff_preview_for_row(
                    rows_by_path.get(path, {}), context
                )
                view.setHtml(render(_resume_history_markdown(context, diff_preview)))
                prompt_editor.setPlainText(_resume_task_prompt(context))
                copy_button.setEnabled(True)
                resume_button.setEnabled(True)
            except Exception as exc:
                view.setHtml(render(f"{_tf('build_resume_context_failed', error=exc)}"))
                prompt_editor.clear()
                copy_button.setEnabled(False)
                resume_button.setEnabled(False)

        def resume_selected() -> None:
            item = run_list.currentItem()
            if item is None:
                return
            path = str(item.data(Qt.ItemDataRole.UserRole) or "")
            context = contexts.get(path)
            if context is None:
                context = build_resume_context(path)
            prompt = prompt_editor.toPlainText().strip() or _resume_task_prompt(context)
            dialog.accept()
            self._submit_text(prompt, clear_input=False)

        def copy_prompt() -> None:
            text = prompt_editor.toPlainText().strip()
            if text:
                QApplication.clipboard().setText(text)

        copy_button.clicked.connect(copy_prompt)
        resume_button.clicked.connect(resume_selected)
        run_list.currentItemChanged.connect(lambda current, _previous: show_selected(current))

        if candidates:
            for row in candidates:
                item = QListWidgetItem(_resume_history_item_label(row))
                item.setData(Qt.ItemDataRole.UserRole, str(row.get("path") or ""))
                item.setToolTip(str(row.get("path") or ""))
                run_list.addItem(item)
            run_list.setCurrentRow(0)
        else:
            view.setHtml(render(f"### {_t('resume_history_title')}\n\n{_t('no_resume_history')}"))
            prompt_editor.clear()

        dialog.exec()

    def _return_dialog_to_activity(self, dialog: QDialog) -> None:
        dialog.reject()
        QTimer.singleShot(0, self._show_activity_panel)

    def _return_rollback_history_to_activity(self) -> None:
        self._toggle_rollback_history_panel(False)
        QTimer.singleShot(0, self._show_activity_panel)

    def _show_activity_panel(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(_t("activity_title"))
        dialog.resize(520, 360)
        dialog.setStyleSheet(_dialog_style())

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel(_t("activity_title"))
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 14px; font-weight: 800;")
        layout.addWidget(title)

        intro = QLabel(_t("activity_intro"))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 12px;")
        layout.addWidget(intro)

        workspace = self._workspace_tools_for_session()
        diff_count: int | None = None
        diff_paths: list[str] | None = None
        rollback_count: int | None = None
        if workspace is not None:
            try:
                diff_preview = workspace.preview_rollback_session(limit=80)
                raw_paths = diff_preview.get("paths") if isinstance(diff_preview.get("paths"), list) else []
                diff_paths = [str(path) for path in raw_paths]
                diff_count = int(diff_preview.get("path_count") or len(diff_paths))
            except Exception:
                diff_paths = None
                diff_count = None
            try:
                rollback_history = workspace.list_rollback_history(limit=40, include_inactive=True)
                rollback_count = int(
                    rollback_history.get("count")
                    if rollback_history.get("count") is not None
                    else len(rollback_history.get("entries") or [])
                )
            except Exception:
                rollback_count = None

        resume_candidates: list[dict[str, Any]] | None = None
        resume_count: int | None = None
        analytics: dict[str, Any] | None = None
        try:
            resume_candidates = _resume_history_candidates(
                list_run_history(limit=80),
                workspace_root=self._current_workspace_root(),
            )
            resume_count = len(resume_candidates)
        except Exception:
            resume_candidates = None
            resume_count = None
        try:
            analytics = build_run_analytics(limit=80, workspace_root=self._current_workspace_root())
        except Exception:
            analytics = None

        def add_activity_row(
            label_key: str,
            summary: str,
            tip_key: str,
            action: Any,
            detail_lines: list[str] | None = None,
        ) -> None:
            row = QFrame()
            row.setStyleSheet(
                f"background: {C_BG_SURFACE}; border: 1px solid {C_BORDER}; border-radius: 14px;"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)
            row_layout.setSpacing(12)

            text_stack = QVBoxLayout()
            text_stack.setContentsMargins(0, 0, 0, 0)
            text_stack.setSpacing(4)

            label = QLabel(_t(label_key))
            label.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 12px; font-weight: 800;")
            text_stack.addWidget(label)

            status = QLabel(summary)
            status.setStyleSheet(f"color: {C_ACCENT}; font-size: 11px; font-weight: 800;")
            text_stack.addWidget(status)

            description = QLabel(_t(tip_key))
            description.setWordWrap(True)
            description.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 11px;")
            text_stack.addWidget(description)

            for line in detail_lines or []:
                detail = QLabel(line)
                detail.setWordWrap(True)
                detail.setStyleSheet(
                    f"color: {C_TEXT_PLACEHOLDER}; font-size: 10.5px; padding-left: 6px;"
                )
                text_stack.addWidget(detail)

            row_layout.addLayout(text_stack, 1)

            button = QPushButton(_t("execute"))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(_button_style("secondary", compact=True))
            button.clicked.connect(lambda _checked=False: (dialog.accept(), action()))
            row_layout.addWidget(button)

            layout.addWidget(row)

        add_activity_row(
            "activity_open_diff",
            _activity_status_summary("diff", count=diff_count, unavailable=workspace is None),
            "diff_review_tip",
            self._show_current_diff_review,
            _activity_recent_path_lines(diff_paths or []) if diff_paths is not None else None,
        )
        add_activity_row(
            "activity_open_resume",
            _activity_status_summary("resume", count=resume_count),
            "resume_history_tip",
            self._show_resume_history_picker,
            _activity_recent_resume_lines(resume_candidates or []) if resume_candidates is not None else None,
        )
        add_activity_row(
            "activity_open_history",
            _activity_status_summary("rollback", count=rollback_count, unavailable=workspace is None),
            "rollback_history_tip",
            lambda: self._toggle_rollback_history_panel(True),
        )
        add_activity_row(
            "activity_open_analytics",
            _activity_analytics_summary(analytics),
            "run_analytics_tip",
            self._show_run_analytics,
        )

        layout.addStretch(1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)

        back_button = QPushButton(_t("activity_back"))
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        back_button.setStyleSheet(_button_style("secondary", compact=True))
        back_button.clicked.connect(dialog.reject)
        footer.addWidget(back_button)
        layout.addLayout(footer)

        dialog.exec()

    def _show_run_analytics(self) -> None:
        try:
            analytics = build_run_analytics(limit=80, workspace_root=self._current_workspace_root())
            markdown = format_run_analytics_markdown(analytics)
        except Exception as exc:
            QMessageBox.warning(self, "kagent", _tf("read_run_log_failed", error=exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(_t("run_analytics_title"))
        dialog.resize(840, 660)
        dialog.setStyleSheet(_dialog_style())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(_t("run_analytics_title"))
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 14px; font-weight: 800;")
        layout.addWidget(title)

        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setStyleSheet(_text_view_style())
        view.setHtml(render(markdown))
        layout.addWidget(view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        back_activity_button = buttons.addButton(
            _t("activity_back_to_activity"), QDialogButtonBox.ButtonRole.ActionRole
        )
        back_activity_button.clicked.connect(
            lambda _checked=False, dlg=dialog: self._return_dialog_to_activity(dlg)
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _show_current_diff_review(self) -> None:
        workspace = self._workspace_tools_for_session()
        if workspace is None:
            QMessageBox.information(self, "kagent", _t("no_active_session"))
            return
        try:
            preview = workspace.preview_rollback_session(limit=80)
            markdown = _diff_review_markdown(preview)
        except Exception as exc:
            QMessageBox.warning(self, "kagent", _tf("diff_review_failed", error=exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(_t("current_diff_review"))
        dialog.resize(840, 660)
        dialog.setStyleSheet(_dialog_style())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(_t("current_diff_review"))
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 14px; font-weight: 800;")
        layout.addWidget(title)

        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setStyleSheet(_text_view_style())
        view.setHtml(render(markdown))
        layout.addWidget(view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        back_activity_button = buttons.addButton(
            _t("activity_back_to_activity"), QDialogButtonBox.ButtonRole.ActionRole
        )
        back_activity_button.clicked.connect(
            lambda _checked=False, dlg=dialog: self._return_dialog_to_activity(dlg)
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()


    # ==================== State ====================

    def _is_busy(self) -> bool:
        return self._send_locked or bool(self.worker and self.worker.isRunning())

    def _sync_send_button_style(self):
        if self._is_busy():
            self.send_btn.setStyleSheet(_button_style("primary", radius=14))
        else:
            self.send_btn.setStyleSheet(_button_style("primary", radius=14))

    def _sync_stop_button_style(self):
        if self._is_busy():
            if self._stop_requested:
                self.stop_btn.setStyleSheet(
                    "background: rgba(148, 163, 184, 0.18); color: #94A3B8; "
                    "border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 14px; "
                    "padding: 8px 18px; font-size: 13px; font-weight: 800;"
                )
                self.stop_btn.setText(_t("stopping"))
            else:
                self.stop_btn.setStyleSheet(_button_style("danger", radius=14))
                self.stop_btn.setText(_t("stop"))
        else:
            self.stop_btn.setStyleSheet(_button_style("secondary", radius=14))
            self.stop_btn.setText(_t("stop"))

    def _sync_mode_button_style(self):
        if self.agent_btn.isChecked():
            self.agent_btn.setStyleSheet(
                "background: rgba(56, 189, 248, 0.14); color: #BAE6FD; "
                "border: 1px solid rgba(56, 189, 248, 0.34); border-radius: 12px; "
                "padding: 8px 12px; font-size: 12px; font-weight: 700;"
            )
        else:
            self.agent_btn.setStyleSheet(
                "background: rgba(255, 255, 255, 0.04); color: #94A3B8; "
                f"border: 1px solid {C_BORDER}; border-radius: 12px; padding: 8px 12px; "
                "font-size: 12px; font-weight: 800;"
            )

    def _set_busy_controls(self, busy: bool):
        self.new_btn.setEnabled(not busy)
        self.session_list.setEnabled(not busy)
        if hasattr(self, "settings_btn"):
            self.settings_btn.setEnabled(not busy)
        if hasattr(self, "permission_menu_btn"):
            self.permission_menu_btn.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy and not self._stop_requested)
        self._sync_mode_button_style()
        self._sync_send_button_style()
        self._sync_stop_button_style()

    def _legacy_refresh_chat_header(self):
        title = self._current_session_title()
        count = len(db.get_messages(self.current_session)) if self.current_session else 0

        self.chat_title_label.setText(title)
        self.chat_subtitle_label.setText(f"{self._model_reasoning_label()} ? Workspace ? {count} ??? ? {self._activity}")
        self.chat_mode_chip.setText(_t("workspace"))
        self._sync_workspace_mode_chip()

    def _legacy_update_status(self):
        self.status_count.setText(self._permission_summary())

    # ==================== Send Flow ====================

    def _legacy_stopped_message_for_worker(self, worker: AgentWorker | None) -> str:
        return "??????"

    def _legacy_finalize_stopped_worker(self, worker: AgentWorker | None):
        stopped_text = self._stopped_message_for_worker(worker)
        card = getattr(self, "_streaming_card", None)
        row = getattr(self, "_streaming_row", None)
        if card is not None and not self._streaming_buf.strip():
            card.update_body(stopped_text, streaming=False)
            if row is not None:
                self.chat_scroll.verticalScrollBar().setValue(
                    self.chat_scroll.verticalScrollBar().maximum()
                )
        elif card is None:
            msgs = db.get_messages(self.current_session) if self.current_session else []
            self._render_messages(msgs, thinking=True)
            card = getattr(self, "_streaming_card", None)
            row = getattr(self, "_streaming_row", None)
            if card is not None:
                card.update_body(stopped_text, streaming=False)
                if row is not None:
                    self.chat_scroll.verticalScrollBar().setValue(
                        self.chat_scroll.verticalScrollBar().maximum()
                    )

        trace = self._agent_trace_card if isinstance(worker, AgentWorker) else None
        if trace is not None:
            trace.set_state(_t("stopped"), kind="active")

        self._activity = "Stopped"
        self._send_locked = False
        self.worker = None
        self._stop_requested = False
        self._set_busy_controls(False)
        self._streaming_buf = ""
        self._streaming_time = ""
        self._streaming_card = None
        self._streaming_row = None
        self._refresh_chat_header()
        self._update_status()
        self._refresh_rollback_history_panel()
        self.input.setFocus()


    def _release_detached_worker(self, worker: AgentWorker | None) -> None:
        if worker is None:
            return
        if worker in self._detached_workers:
            self._detached_workers.remove(worker)
            worker.deleteLater()

    def _track_detached_worker(self, worker: AgentWorker | None) -> None:
        if worker is None or worker in self._detached_workers:
            return
        self._detached_workers.append(worker)

    def _attach_worker_signals(self, worker: AgentWorker) -> None:
        worker.done.connect(
            lambda full, current_worker=worker: self._on_done(current_worker, full)
        )
        worker.error.connect(
            lambda msg, current_worker=worker: self._on_error(current_worker, msg)
        )
        worker.title_ready.connect(self._on_title)
        worker.tool_event.connect(
            lambda event, current_worker=worker: self._on_tool_event(current_worker, event)
        )
        worker.finished.connect(
            lambda current_worker=worker: self._release_detached_worker(current_worker)
        )

    def _on_stop_clicked(self):
        if not self._is_busy() or self.worker is None or self._stop_requested:
            return

        worker = self.worker
        self._stop_requested = True
        self._activity = "Stopping"
        worker.stop()
        self._set_busy_controls(True)
        self._refresh_chat_header()
        QTimer.singleShot(
            WORKER_STOP_GRACE_MS,
            lambda current_worker=worker: self._force_finalize_stopping_worker(current_worker),
        )

    def _force_finalize_stopping_worker(self, worker: AgentWorker | None) -> None:
        if worker is None:
            return
        if self.worker is not worker or not self._stop_requested:
            return
        self._track_detached_worker(worker)
        self._finalize_stopped_worker(worker)

    def _on_tool_event(self, worker: AgentWorker, event: dict[str, Any]):
        if worker is not self.worker:
            return

        trace = self._ensure_agent_trace_card()
        if trace is None:
            return

        self._apply_tool_event(trace, event)
        self._tool_trace_events.append(dict(event))
        if str(event.get("type") or "").strip() == "tool_result":
            name = str(event.get("name") or "").strip()
            if name in {
                "write_file",
                "apply_patch",
                "rename_path",
                "copy_path",
                "delete_path",
                "make_directory",
                "rollback_last_change",
                "rollback_change",
                "list_rollback_history",
                "preview_rollback_change",
            }:
                self._refresh_rollback_history_panel()

        self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        )

    def _submit_text(self, text: str, clear_input: bool = False) -> None:
        if self._is_busy():
            return
        if not self.current_session:
            self.new_session()
        if not self.current_session:
            return

        normalized = str(text or "").strip()
        if not normalized:
            return

        self.agent_btn.setChecked(True)
        self._stop_requested = False
        if clear_input:
            self.input.clear()
        self._streaming_buf = ""
        self._streaming_time = datetime.now().strftime("%H:%M")
        self._activity = "Working"
        self._reset_tool_trace()
        self._send_locked = True
        self._set_busy_controls(True)

        db.save_message(self.current_session, "user", normalized)
        history = db.get_messages(self.current_session)
        self._render_messages(history, thinking=True)

        worker = AgentWorker(
            self.current_session,
            normalized,
            history,
            workspace_root=self._current_workspace_root(),
            model=self._selected_model,
            reasoning_effort=self._selected_reasoning_effort,
        )
        self.worker = worker
        self._attach_worker_signals(worker)

        QTimer.singleShot(
            THINKING_PLACEHOLDER_DELAY_MS,
            lambda current_worker=worker: self._start_worker(current_worker),
        )

    def on_send(self):
        text = self.input.toPlainText().strip()
        if hasattr(self, "slash_command_list"):
            self.slash_command_list.setVisible(False)
            self._sync_slash_command_layout(False)
        self._submit_text(text, clear_input=True)

    def _start_worker(self, worker: AgentWorker | None):
        if worker is None:
            return
        if self.worker is not worker:
            return
        if getattr(worker, "_stop", False):
            self._finalize_stopped_worker(worker)
            return
        worker.start()


    def _on_done(self, worker: AgentWorker, full: str):
        if worker is not self.worker:
            return

        was_stopped = bool(self._stop_requested or getattr(worker, "_stop", False))
        if was_stopped and not full.strip():
            self._finalize_stopped_worker(worker)
            return

        card = getattr(self, "_streaming_card", None)
        row = getattr(self, "_streaming_row", None)
        self._activity = "Stopped" if was_stopped else "Ready"
        if card is not None:
            card.update_body(full, streaming=False)
            if row is not None:
                self.chat_scroll.verticalScrollBar().setValue(
                    self.chat_scroll.verticalScrollBar().maximum()
                )
        else:
            msgs = db.get_messages(self.current_session) if self.current_session else []
            self._render_messages(msgs)

        trace = self._agent_trace_card
        if trace is not None:
            trace.set_state(
                _t("stopped") if was_stopped else _t("done"),
                kind="active" if was_stopped else "done",
            )

        self._send_locked = False
        self.worker = None
        self._stop_requested = False
        self._set_busy_controls(False)
        self._sync_send_button_style()
        self._streaming_buf = ""
        self._streaming_time = ""
        self._streaming_card = None
        self._streaming_row = None
        self._refresh_chat_header()
        self._update_status()
        self._refresh_rollback_history_panel()
        self.input.setFocus()

    def _legacy_on_error(self, worker: AgentWorker, msg: str):
        if worker is not self.worker:
            return
        if self._stop_requested:
            self._finalize_stopped_worker(worker)
            return

        msgs = db.get_messages(self.current_session) if self.current_session else []
        self._activity = "Ready"
        self._render_messages(msgs, error_text=msg)

        trace = self._agent_trace_card
        if trace is not None:
            trace.set_state(_t("failed"), kind="error")

        self._send_locked = False
        self.worker = None
        self._stop_requested = False
        self._set_busy_controls(False)
        self._sync_send_button_style()
        self._streaming_buf = ""
        self._streaming_time = ""
        self._refresh_rollback_history_panel()
        self.input.setFocus()
        QMessageBox.warning(self, "kagent", _tf("call_failed", error=msg))

    def _refresh_chat_header(self):
        title = self._current_session_title()
        count = len(db.get_messages(self.current_session)) if self.current_session else 0

        self.chat_title_label.setText(title)
        self.chat_subtitle_label.setText(
            f"{self._model_reasoning_label()} | {self._workspace_header_label()} | {self._activity_label()}"
        )
        if hasattr(self, "workspace_btn"):
            self.workspace_btn.setText(_workspace_button_label(self._current_workspace_root()))
            self.workspace_btn.setToolTip(
                _tf("workspace_button_tooltip", path=self._current_workspace_root())
                if self._current_workspace_root()
                else _t("no_project_tooltip")
            )
        self._sync_workspace_mode_chip()

    def _update_status(self):
        self.status_count.setText(self._permission_summary())

    def _stopped_message_for_worker(self, worker: AgentWorker | None) -> str:
        return _t("stopped")

    def _finalize_stopped_worker(self, worker: AgentWorker | None):
        stopped_text = self._stopped_message_for_worker(worker)
        card = getattr(self, "_streaming_card", None)
        row = getattr(self, "_streaming_row", None)
        if card is not None and not self._streaming_buf.strip():
            card.update_body(stopped_text, streaming=False)
            if row is not None:
                self.chat_scroll.verticalScrollBar().setValue(
                    self.chat_scroll.verticalScrollBar().maximum()
                )
        elif card is None:
            msgs = db.get_messages(self.current_session) if self.current_session else []
            self._render_messages(msgs, thinking=True)
            card = getattr(self, "_streaming_card", None)
            row = getattr(self, "_streaming_row", None)
            if card is not None:
                card.update_body(stopped_text, streaming=False)
                if row is not None:
                    self.chat_scroll.verticalScrollBar().setValue(
                        self.chat_scroll.verticalScrollBar().maximum()
                    )

        trace = self._agent_trace_card
        if trace is not None:
            trace.set_state(_t("stopped"), kind="active")

        self._activity = "Stopped"
        self._send_locked = False
        self.worker = None
        self._stop_requested = False
        self._set_busy_controls(False)
        self._streaming_buf = ""
        self._streaming_time = ""
        self._streaming_card = None
        self._streaming_row = None
        self._refresh_chat_header()
        self._update_status()
        self._refresh_rollback_history_panel()
        self.input.setFocus()

    def _on_error(self, worker: AgentWorker, msg: str):
        if worker is not self.worker:
            return
        if self._stop_requested:
            self._finalize_stopped_worker(worker)
            return

        msgs = db.get_messages(self.current_session) if self.current_session else []
        self._activity = "Ready"
        self._render_messages(msgs, error_text=msg)

        trace = self._agent_trace_card
        if trace is not None:
            trace.set_state(_t("failed"), kind="error")

        self._send_locked = False
        self.worker = None
        self._stop_requested = False
        self._set_busy_controls(False)
        self._sync_send_button_style()
        self._streaming_buf = ""
        self._streaming_time = ""
        self._refresh_rollback_history_panel()
        self.input.setFocus()
        QMessageBox.warning(self, "kagent", _tf("call_failed", error=msg))

    def _on_title(self, title: str):
        self._load_sessions()
        self._refresh_chat_header()

    # ==================== Qt ====================

    def _is_title_bar_drag_area(self, position: QPoint) -> bool:
        if not hasattr(self, "title_bar") or not self.title_bar.geometry().contains(position):
            return False
        child = self.childAt(position)
        return not isinstance(child, QPushButton)

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._is_title_bar_drag_area(event.position().toPoint())
        ):
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_frame = self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_global is not None and self._drag_start_frame is not None:
            if self.isMaximized():
                self.showNormal()
                self.maximize_btn.setText("[]")
                self._drag_start_frame = self.frameGeometry().topLeft()
                self._drag_start_global = event.globalPosition().toPoint()
            delta = event.globalPosition().toPoint() - self._drag_start_global
            self.move(self._drag_start_frame + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start_global = None
        self._drag_start_frame = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._is_title_bar_drag_area(event.position().toPoint())
        ):
            self._toggle_window_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def closeEvent(self, e):
        workers: list[AgentWorker] = []
        if self.worker is not None:
            workers.append(self.worker)
        for worker in list(self._detached_workers):
            if worker not in workers:
                workers.append(worker)
        for worker in workers:
            worker.stop()
        for worker in workers:
            if worker.isRunning():
                worker.wait(2000)
        super().closeEvent(e)
