import html
import json
import re
import uuid
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QEvent, Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import db
from ..agent import WorkspaceTools
from ..config import MODEL
from .agent_worker import AgentWorker
from .chat_worker import ChatWorker
from .markdown_view import highlight_css, render

THINKING_PLACEHOLDER_DELAY_MS = 220
STREAM_RENDER_INTERVAL_MS = 40
WORKER_STOP_GRACE_MS = 1500


C_BG_ROOT = "#070B14"
C_BG_PANEL = "#0C1322"
C_BG_PANEL_ALT = "#0E1626"
C_BG_SIDEBAR = "#09101B"
C_BG_SURFACE = "#111827"
C_BG_SURFACE_ALT = "#162033"
C_BG_INPUT = "#0F172A"
C_BG_INPUT_WRAP = "#101B2D"
C_TEXT_MAIN = "#E5E7EB"
C_TEXT_SUB = "#94A3B8"
C_TEXT_PLACEHOLDER = "#64748B"
C_BORDER = "#223047"
C_BORDER_SOFT = "#1B2639"
C_ACCENT = "#8B5CF6"
C_ACCENT_HOVER = "#7C3AED"
C_ACCENT_2 = "#2563EB"
C_USER_ACCENT = "#0EA5E9"
C_ERROR = "#F87171"


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
        return "刚刚"
    raw = str(created_at).strip().replace("T", " ")
    try:
        return datetime.fromisoformat(raw).strftime("%H:%M")
    except Exception:
        return raw


def _chip_label(text: str, fg: str, bg: str, border: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    label.setStyleSheet(
        f"background: {bg}; color: {fg}; border: 1px solid {border}; "
        "border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 700;"
    )
    return label


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
        return text[:limit] + "\n... (truncated)"
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


def _rollback_change_type_label(action: str) -> str:
    mapping = {
        "update": "Text update",
        "restore_file": "Restore file",
        "delete_file": "Delete file",
        "restore_directory": "Restore folder",
        "delete_directory": "Delete folder",
        "replace_binary": "Replace binary",
        "replace_item": "Replace item",
    }
    return mapping.get(str(action or "").strip(), str(action or "Change"))


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
                    "label": f"差异 #{rollback_id}",
                    "prompt": (
                        f"请直接调用 preview_rollback_change 工具，参数 rollback_id={int(rollback_id)}，"
                        "只展示差异预览，不要执行回滚。"
                    ),
                }
            )
            if bool(entry.get("available", False)):
                actions.append(
                    {
                        "label": f"恢复 #{rollback_id}",
                        "prompt": (
                            f"请直接调用 rollback_change 工具，参数 rollback_id={int(rollback_id)}，"
                            "恢复到这个版本，然后给我结果。"
                        ),
                    }
                )
        return actions

    if name == "preview_rollback_change":
        rollback_id = result.get("rollback_id")
        if rollback_id and bool(result.get("available", False)):
            actions.append(
                {
                    "label": "恢复这个版本",
                    "prompt": (
                        f"请直接调用 rollback_change 工具，参数 rollback_id={int(rollback_id)}，"
                        "恢复到这个版本，然后给我结果。"
                    ),
                }
            )
        return actions

    if name in {"rollback_last_change", "rollback_change"}:
        undo_rollback_id = result.get("undo_rollback_id")
        if undo_rollback_id:
            actions.append(
                {
                    "label": "撤销这次回滚",
                    "prompt": (
                        f"请直接调用 rollback_change 工具，参数 rollback_id={int(undo_rollback_id)}，"
                        "撤销刚才那次回滚，然后给我结果。"
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
) -> str:
    parts: list[str] = [f"### `{name}`"]
    if round_idx is not None:
        parts.append(f"**轮次** 第 {round_idx} 轮")
    if status:
        parts.append(f"**状态** {status}")
    if preview:
        parts.append("**预览**")
        parts.append(_preview_markdown_block(preview))
    if args is not None:
        parts.append("**输入**")
        parts.append(f"```json\n{_pretty_json(args)}\n```")
    if result is not None:
        parts.append("**结果**")
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
) -> str:
    if isinstance(result, dict):
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
            return _single_line(f"错误：{error_text}")
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
            return _single_line(f"搜索：{args['query']}")

    fallback = {
        "预览": f"{name} 预览中",
        "执行中": f"{name} 执行中",
        "成功": f"{name} 已完成",
        "失败": f"{name} 执行失败",
    }
    return fallback.get(status, f"{name} {status}")


def _assistant_body_html(content: str, streaming: bool, thinking: bool) -> str:
    if thinking:
        body = '<span class="typing">正在思考…</span>'
    elif streaming:
        body = html.escape(content).replace("\n", "<br>")
        if not body:
            body = '<span class="typing">正在思考…</span>'
    else:
        body = render(content)
        if not body:
            body = '<span class="typing">准备回复…</span>'
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
    def __init__(self, on_send):
        super().__init__()
        self.setPlaceholderText("输入消息… Enter 发送 · Shift+Enter 换行")
        self.setMinimumHeight(62)
        self.setMaximumHeight(88)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.on_send = on_send

    def keyPressEvent(self, e):
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
        body = html_text or '<span class="typing">正在思考…</span>'
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
            body_html = f'<div class="error-box">错误：{html.escape(content)}</div>'
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

        role_label = QLabel("kagent" if role == "assistant" else "You")
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
        self._summary_full = "等待工具输出..."
        self._approval_pending = False
        self._actions: list[dict[str, str]] = []
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setFixedWidth(width)
        self.setStyleSheet(
            "background: rgba(9, 16, 27, 0.92); "
            f"border: 1px solid {C_BORDER_SOFT}; border-radius: 16px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_btn.setToolTip("展开工具详情")
        self.toggle_btn.setAutoRaise(True)
        self.toggle_btn.clicked.connect(self._set_expanded)

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

        self.status_chip = QLabel("执行中")
        self.status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.status_chip.setStyleSheet(
            "background: rgba(124, 58, 237, 0.16); color: #E9D5FF; "
            "border: 1px solid rgba(124, 58, 237, 0.30); "
            "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
        )

        header.addWidget(self.toggle_btn)
        header.addWidget(self.name_label)
        if round_idx is not None:
            self.round_label.setText(f"第 {round_idx} 轮")
            header.addWidget(self.round_label)
        header.addWidget(self.summary_label, 1)
        header.addStretch(1)
        header.addWidget(self.status_chip)
        layout.addLayout(header)

        self.body = MessageBody()
        self.body.set_content(
            '<span class="typing">等待工具输出...</span>',
            max(220, width - 24),
            text_color=C_TEXT_MAIN,
        )
        self.body.setVisible(False)
        layout.addWidget(self.body)

        self.approval_bar = QWidget()
        approval_layout = QHBoxLayout(self.approval_bar)
        approval_layout.setContentsMargins(0, 0, 0, 0)
        approval_layout.setSpacing(8)

        self.approval_label = QLabel("需要你的确认后继续执行")
        self.approval_label.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 12px;")

        self.allow_btn = QPushButton("Allow")
        self.allow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.allow_btn.setStyleSheet(
            "background: rgba(34, 197, 94, 0.16); color: #DCFCE7; "
            "border: 1px solid rgba(34, 197, 94, 0.28); "
            "border-radius: 10px; padding: 6px 12px; font-size: 11px; font-weight: 700;"
        )
        self.allow_btn.clicked.connect(lambda: self._submit_approval(True))

        self.reject_btn = QPushButton("Reject")
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
        self.toggle_btn.setToolTip("收起工具详情" if expanded else "展开工具详情")
        self.updateGeometry()

    def _submit_approval(self, approved: bool) -> None:
        if not self._approval_pending:
            return
        self._approval_pending = False
        self.allow_btn.setEnabled(False)
        self.reject_btn.setEnabled(False)
        self.approval_label.setText(
            "已允许，继续执行中…" if approved else "已拒绝，正在返回结果…"
        )
        self.approval_decided.emit(self.call_id, approved)

    def _submit_action(self, action: dict[str, str]) -> None:
        if not isinstance(action, dict):
            return
        self.action_requested.emit(dict(action))

    def set_approval_pending(self, pending: bool) -> None:
        self._approval_pending = pending
        if pending:
            self.approval_label.setText("需要你的确认后继续执行")
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

        title = QLabel("蹇€熸搷浣?")
        title.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 12px;")
        self.actions_layout.addWidget(title)

        for idx in range(0, len(self._actions), 2):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            for action in self._actions[idx : idx + 2]:
                btn = QPushButton(str(action.get("label") or "鎵ц"))
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
    ) -> None:
        if round_idx is not None:
            self.round_label.setText(f"第 {round_idx} 轮")
        self.status_chip.setText(status)
        if preview is not None:
            self._preview = preview
        status_key = status.strip().lower()
        if error or status_key in {"rejected", "failed"}:
            chip_style = (
                "background: rgba(248, 113, 113, 0.16); color: #FCA5A5; "
                "border: 1px solid rgba(248, 113, 113, 0.30); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        elif status == "成功":
            chip_style = (
                "background: rgba(34, 197, 94, 0.14); color: #BBF7D0; "
                "border: 1px solid rgba(34, 197, 94, 0.28); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        elif status == "失败":
            chip_style = (
                "background: rgba(248, 113, 113, 0.16); color: #FCA5A5; "
                "border: 1px solid rgba(248, 113, 113, 0.30); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        else:
            chip_style = (
                "background: rgba(124, 58, 237, 0.16); color: #E9D5FF; "
                "border: 1px solid rgba(124, 58, 237, 0.30); "
                "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
            )
        self.status_chip.setStyleSheet(chip_style)
        self._summary_full = _tool_event_summary(
            self.name_label.text(),
            status,
            args=args,
            result=result,
            preview=self._preview,
        )
        self._refresh_summary_label()

        body_md = _tool_event_markdown(
            self.name_label.text(),
            args=args,
            result=result,
            round_idx=round_idx,
            status=status,
            preview=self._preview,
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
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setFixedWidth(width)
        self.setStyleSheet(
            "background: rgba(15, 23, 42, 0.94); "
            f"border: 1px solid rgba(124, 58, 237, 0.24); border-radius: 20px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("Agent 执行日志")
        title.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #E9D5FF;")

        self.state_chip = QLabel("执行中")
        self.state_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.state_chip.setStyleSheet(
            "background: rgba(124, 58, 237, 0.16); color: #E9D5FF; "
            "border: 1px solid rgba(124, 58, 237, 0.30); "
            "border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 700;"
        )

        self.hint = QLabel("等待工具调用")
        self.hint.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 11px;")

        header.addWidget(title)
        header.addWidget(self.hint)
        header.addStretch(1)
        header.addWidget(self.state_chip)
        layout.addLayout(header)

        self.entries_layout = QVBoxLayout()
        self.entries_layout.setSpacing(10)
        layout.addLayout(self.entries_layout)

        self.empty_label = QLabel("Agent 正在分析任务，工具调用会显示在这里。")
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 12px;")
        layout.addWidget(self.empty_label)

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
                "background: rgba(124, 58, 237, 0.16); color: #E9D5FF; "
                "border: 1px solid rgba(124, 58, 237, 0.30); "
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
        )
        self._sync_empty()
        return entry


class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("kagent")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        self.current_session: str | None = None
        self.worker: ChatWorker | AgentWorker | None = None
        self._detached_workers: list[ChatWorker | AgentWorker] = []
        self._streaming_buf = ""
        self._streaming_time = ""
        self._activity = "就绪"
        self._send_locked = False
        self._stop_requested = False
        self._stream_flush_pending = False
        self._stream_last_painted = ""
        self._agent_trace_card: ToolTraceCard | None = None
        self._agent_trace_row: QWidget | None = None
        self._tool_trace_events: list[dict[str, Any]] = []
        self._rollback_history_visible = False
        self._rollback_history_items: list[dict[str, Any]] = []
        self._selected_rollback_id: int | None = None
        self._render_seq = 0

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

        layout.addWidget(self._build_title_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_chat_area())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 900])
        layout.addWidget(splitter, 1)

        layout.addWidget(self._build_status_bar())

        self.new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_shortcut.activated.connect(self.new_session)

        self.delete_shortcut = QShortcut(QKeySequence("Delete"), self.session_list)
        self.delete_shortcut.activated.connect(self._delete_current_session)

        self._load_sessions()
        sessions = db.list_sessions()
        if sessions:
            self._open_session(sessions[0]["id"])
        else:
            self._render_messages([])

        self._refresh_chat_header()
        self._update_status()

    # ==================== UI ====================

    def _build_title_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(52)
        bar.setStyleSheet(
            f"background: rgba(9, 16, 27, 0.94); border-bottom: 1px solid {C_BORDER};"
        )

        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(12)

        brand = QLabel("K")
        brand.setFixedSize(26, 26)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}); color: #fff; "
            "border-radius: 13px; font-size: 13px; font-weight: 800;"
        )
        h.addWidget(brand)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        title_stack.setContentsMargins(0, 0, 0, 0)

        title = QLabel("kagent")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_TEXT_MAIN};")

        subtitle = QLabel("Local coding workspace")
        subtitle.setFont(QFont("Microsoft YaHei", 8))
        subtitle.setStyleSheet(f"color: {C_TEXT_SUB};")

        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        h.addLayout(title_stack)
        h.addStretch(1)

        for icon, tip in (("⋯", "更多"), ("⚙", "设置（开发中）")):
            btn = QPushButton(icon)
            btn.setFixedSize(34, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"background: rgba(255, 255, 255, 0.04); color: {C_TEXT_SUB}; "
                f"border: 1px solid {C_BORDER}; border-radius: 10px; font-size: 15px;"
            )
            btn.setToolTip(tip)
            btn.clicked.connect(lambda *_: QMessageBox.information(self, "kagent", "这个按钮还在开发中。"))
            h.addWidget(btn)

        return bar

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(
            f"background: rgba(9, 16, 27, 0.94); border-right: 1px solid {C_BORDER};"
        )

        v = QVBoxLayout(sidebar)
        v.setContentsMargins(12, 14, 12, 12)
        v.setSpacing(10)

        self.new_btn = QPushButton("+  新建会话")
        self.new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_btn.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}); "
            "color: #fff; border: none; border-radius: 14px; padding: 12px 14px; "
            "font-size: 13px; font-weight: 800;"
        )
        self.new_btn.clicked.connect(self.new_session)
        v.addWidget(self.new_btn)

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
    padding: 12px 12px;
    margin: 4px 4px;
    border-radius: 12px;
}}
QListWidget::item:hover {{
    background: rgba(255, 255, 255, 0.04);
}}
QListWidget::item:selected {{
    background: rgba(124, 58, 237, 0.16);
    color: #F5F3FF;
}}
""".strip()
        )
        self.session_list.itemClicked.connect(self._on_session_clicked)
        v.addWidget(self.session_list, 1)

        tip = QLabel("Ctrl+N 新建 · Delete 删除")
        tip.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 11px; padding: 4px 2px;")
        v.addWidget(tip)

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
    background: {C_BG_PANEL};
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
        self.chat_layout.setContentsMargins(24, 22, 24, 22)
        self.chat_layout.setSpacing(14)
        self.chat_scroll.setWidget(self.chat_content)
        self.chat_scroll.verticalScrollBar().valueChanged.connect(self._update_scroll_to_bottom_button)
        self.chat_scroll.verticalScrollBar().rangeChanged.connect(self._update_scroll_to_bottom_button)
        self.chat_scroll.viewport().installEventFilter(self)

        self.scroll_bottom_btn = QPushButton("↓", self.chat_scroll.viewport())
        self.scroll_bottom_btn.setFixedSize(38, 38)
        self.scroll_bottom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scroll_bottom_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll_bottom_btn.setToolTip("回到底部")
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

        title = QLabel("Rollback History")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_TEXT_MAIN};")
        header.addWidget(title)

        self.rollback_count_label = QLabel("0 entries")
        self.rollback_count_label.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 11px;")
        header.addWidget(self.rollback_count_label)
        header.addStretch(1)

        self.rollback_refresh_btn = QPushButton("Refresh")
        self.rollback_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_refresh_btn.clicked.connect(self._refresh_rollback_history_panel)
        self.rollback_refresh_btn.setStyleSheet(
            "background: rgba(255, 255, 255, 0.04); color: #E5E7EB; "
            f"border: 1px solid {C_BORDER}; border-radius: 10px; "
            "padding: 6px 10px; font-size: 11px; font-weight: 700;"
        )
        header.addWidget(self.rollback_refresh_btn)

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

        self.rollback_detail_title = QLabel("Select a rollback entry")
        self.rollback_detail_title.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self.rollback_detail_title.setStyleSheet(f"color: {C_TEXT_MAIN};")
        detail_layout.addWidget(self.rollback_detail_title)

        self.rollback_detail_meta = QLabel("The exact file diff for that version will appear here.")
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

        self.rollback_open_trace_btn = QPushButton("Open In Chat")
        self.rollback_open_trace_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_open_trace_btn.clicked.connect(self._open_selected_rollback_preview_in_chat)
        self.rollback_open_trace_btn.setStyleSheet(
            "background: rgba(255, 255, 255, 0.04); color: #E5E7EB; "
            f"border: 1px solid {C_BORDER}; border-radius: 10px; "
            "padding: 7px 12px; font-size: 11px; font-weight: 700;"
        )
        actions.addWidget(self.rollback_open_trace_btn)

        self.rollback_restore_btn = QPushButton("Restore")
        self.rollback_restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_restore_btn.clicked.connect(self._restore_selected_rollback)
        self.rollback_restore_btn.setStyleSheet(
            "background: rgba(124, 58, 237, 0.18); color: #E9D5FF; "
            "border: 1px solid rgba(124, 58, 237, 0.32); border-radius: 10px; "
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
        header.setFixedHeight(74)
        header.setStyleSheet(
            f"background: rgba(10, 16, 27, 0.90); border-bottom: 1px solid {C_BORDER};"
        )

        h = QHBoxLayout(header)
        h.setContentsMargins(22, 14, 22, 14)
        h.setSpacing(12)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        title_stack.setContentsMargins(0, 0, 0, 0)

        self.chat_title_label = QLabel("新会话")
        self.chat_title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.chat_title_label.setStyleSheet(f"color: {C_TEXT_MAIN};")

        self.chat_subtitle_label = QLabel(f"{MODEL} · Chat · 0 条消息 · 就绪")
        self.chat_subtitle_label.setFont(QFont("Microsoft YaHei", 8))
        self.chat_subtitle_label.setStyleSheet(f"color: {C_TEXT_SUB};")

        title_stack.addWidget(self.chat_title_label)
        title_stack.addWidget(self.chat_subtitle_label)
        h.addLayout(title_stack)
        h.addStretch(1)

        self.rollback_history_btn = QPushButton("History")
        self.rollback_history_btn.setCheckable(True)
        self.rollback_history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_history_btn.clicked.connect(self._toggle_rollback_history_panel)
        h.addWidget(self.rollback_history_btn)
        self._sync_rollback_history_button_style()

        self.chat_model_chip = _chip_label(MODEL, "#F5F3FF", "rgba(124, 58, 237, 0.16)", "rgba(124, 58, 237, 0.34)")
        self.chat_mode_chip = _chip_label("Chat", "#DBEAFE", "rgba(37, 99, 235, 0.16)", "rgba(37, 99, 235, 0.34)")
        h.addWidget(self.chat_model_chip)
        h.addWidget(self.chat_mode_chip)

        return header

    def _build_input_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(128)
        bar.setStyleSheet(f"background: rgba(8, 12, 20, 0.96); border-top: 1px solid {C_BORDER};")

        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 14, 18, 16)
        h.setSpacing(12)

        wrap = QFrame()
        wrap.setStyleSheet(
            f"background: rgba(15, 23, 42, 0.92); border: 1px solid {C_BORDER}; border-radius: 22px;"
        )

        w = QVBoxLayout(wrap)
        w.setContentsMargins(16, 14, 16, 12)
        w.setSpacing(10)

        self.input = InputBox(self.on_send)
        self.input.setStyleSheet(
            f"background: transparent; border: none; color: {C_TEXT_MAIN}; "
            f"selection-background-color: rgba(124, 58, 237, 0.32); "
            "font-size: 14px; font-family: 'Microsoft YaHei', 'Segoe UI';"
        )
        w.addWidget(self.input)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        hint = QLabel("Enter 发送 · Shift+Enter 换行")
        hint.setStyleSheet(f"color: {C_TEXT_PLACEHOLDER}; font-size: 11px;")
        actions.addWidget(hint)
        actions.addStretch(1)

        self.agent_btn = QPushButton("Agent")
        self.agent_btn.setCheckable(True)
        self.agent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.agent_btn.setToolTip("切换为代码 agent：可读文件、改文件、运行命令")
        self.agent_btn.toggled.connect(self._sync_mode_button_style)
        self.agent_btn.toggled.connect(self._refresh_chat_header)
        actions.addWidget(self.agent_btn)
        self._sync_mode_button_style()

        self.send_btn = QPushButton("发送")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.on_send)
        actions.addWidget(self.send_btn)

        self.stop_btn = QPushButton("停止")
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
        bar.setFixedHeight(28)
        bar.setStyleSheet(f"background: rgba(8, 12, 20, 0.96); border-top: 1px solid {C_BORDER};")

        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 16, 0)

        self.status_model = _chip_label(MODEL, "#F5F3FF", "rgba(124, 58, 237, 0.16)", "rgba(124, 58, 237, 0.34)")
        h.addWidget(self.status_model)
        h.addStretch(1)

        self.status_count = QLabel("共 0 条消息")
        self.status_count.setObjectName("statusText")
        self.status_count.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 11.5px;")
        h.addWidget(self.status_count)

        return bar

    def _sync_rollback_history_button_style(self) -> None:
        if not hasattr(self, "rollback_history_btn"):
            return
        if self._rollback_history_visible:
            self.rollback_history_btn.setStyleSheet(
                "background: rgba(37, 99, 235, 0.18); color: #DBEAFE; "
                "border: 1px solid rgba(96, 165, 250, 0.38); border-radius: 12px; "
                "padding: 7px 12px; font-size: 12px; font-weight: 800;"
            )
        else:
            self.rollback_history_btn.setStyleSheet(
                "background: rgba(255, 255, 255, 0.04); color: #94A3B8; "
                f"border: 1px solid {C_BORDER}; border-radius: 12px; "
                "padding: 7px 12px; font-size: 12px; font-weight: 800;"
            )

    def _workspace_tools_for_session(self) -> WorkspaceTools | None:
        if not self.current_session:
            return None
        return WorkspaceTools(session_id=self.current_session)

    def _set_rollback_detail_empty(self, text: str = "Select a rollback entry") -> None:
        if not hasattr(self, "rollback_detail_title"):
            return
        self.rollback_detail_title.setText(text)
        self.rollback_detail_meta.setText("The exact file diff for that version will appear here.")
        self.rollback_detail_files.setText("")
        self.rollback_detail_body.setHtml(
            '<div class="typing">Rollback preview will appear here.</div>'
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
        path_label = ", ".join(str(path) for path in paths[:2]) if paths else "No files"
        if len(paths) > 2:
            path_label += f" (+{len(paths) - 2})"
        return (
            f"#{rollback_id}  {source_tool}  [{status}]\n"
            f"{summary}\n"
            f"{path_label}"
        )

    def _refresh_rollback_history_panel(self, select_id: int | None = None) -> None:
        if not hasattr(self, "rollback_list"):
            return

        workspace = self._workspace_tools_for_session()
        if workspace is None:
            self.rollback_list.clear()
            self.rollback_count_label.setText("0 entries")
            self._rollback_history_items = []
            self._selected_rollback_id = None
            self._set_rollback_detail_empty("No active session")
            return

        data = workspace.list_rollback_history(limit=40, include_inactive=True)
        entries = data.get("entries") if isinstance(data.get("entries"), list) else []
        self._rollback_history_items = [item for item in entries if isinstance(item, dict)]
        self.rollback_count_label.setText(f"{len(self._rollback_history_items)} entries")

        current_id = select_id if select_id is not None else self._selected_rollback_id
        self.rollback_list.blockSignals(True)
        self.rollback_list.clear()
        selected_row = -1
        for idx, item in enumerate(self._rollback_history_items):
            list_item = QListWidgetItem(self._format_rollback_list_item(item))
            list_item.setData(Qt.ItemDataRole.UserRole, int(item["rollback_id"]))
            list_item.setToolTip(self._format_rollback_list_item(item))
            list_item.setSizeHint(QSize(0, 66))
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
            self._set_rollback_detail_empty("No rollback history yet")

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
            self._set_rollback_detail_empty("No active session")
            return

        preview = workspace.preview_rollback_change(int(rollback_id))
        self._selected_rollback_id = int(rollback_id)
        status = str(preview.get("status") or "unknown").strip() or "unknown"
        self.rollback_detail_title.setText(
            f"#{rollback_id} · {preview.get('source_tool') or 'rollback'}"
        )
        self.rollback_detail_meta.setText(
            f"Status: {status} | Paths: {int(preview.get('path_count') or 0)} | Created: {preview.get('created_at') or '-'}"
        )

        diff_entries = preview.get("diff_entries") if isinstance(preview.get("diff_entries"), list) else []
        file_lines = []
        for entry in diff_entries:
            if not isinstance(entry, dict):
                continue
            file_lines.append(
                f"- {entry.get('path') or ''} · {_rollback_change_type_label(str(entry.get('action') or ''))}"
            )
        self.rollback_detail_files.setText(
            "\n".join(file_lines) if file_lines else "No file details available"
        )

        md = [
            f"### Rollback #{rollback_id}",
            "",
            f"**Status**: {status}",
            "",
            f"**Summary**: {preview.get('summary') or '-'}",
            "",
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
            f"请直接调用 preview_rollback_change 工具，参数 rollback_id={int(rollback_id)}，"
            "只展示差异预览，不要执行回滚。"
        )
        self._submit_text(prompt, force_agent=True, clear_input=False)

    def _restore_selected_rollback(self) -> None:
        rollback_id = self._selected_rollback_id
        if rollback_id is None:
            return
        prompt = (
            f"请直接调用 rollback_change 工具，参数 rollback_id={int(rollback_id)}，"
            "恢复到这个版本，然后给我结果。"
        )
        self._submit_text(prompt, force_agent=True, clear_input=False)

    def _show_rollback_detail(self, rollback_id: int) -> None:
        workspace = self._workspace_tools_for_session()
        if workspace is None:
            self._set_rollback_detail_empty("No active session")
            return

        preview = workspace.preview_rollback_change(int(rollback_id))
        self._selected_rollback_id = int(rollback_id)
        status = str(preview.get("status") or "unknown").strip() or "unknown"
        source_tool = str(preview.get("source_tool") or "rollback").strip() or "rollback"

        self.rollback_detail_title.setText(f"#{rollback_id} | {source_tool}")
        self.rollback_detail_meta.setText(
            f"Status: {status} | Files: {int(preview.get('path_count') or 0)} | Created: {preview.get('created_at') or '-'}"
        )

        diff_entries = preview.get("diff_entries") if isinstance(preview.get("diff_entries"), list) else []
        file_lines = []
        for entry in diff_entries:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip() or "(unknown path)"
            action = _rollback_change_type_label(str(entry.get("action") or ""))
            file_lines.append(f"- {path} | {action}")
        self.rollback_detail_files.setText(
            "\n".join(file_lines) if file_lines else "No file details available"
        )

        md = [
            f"### Rollback #{rollback_id}",
            "",
            f"**Status**: {status}",
            "",
            f"**Summary**: {preview.get('summary') or '-'}",
            "",
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
            f"Call the preview_rollback_change tool with rollback_id={int(rollback_id)}. "
            "Show the diff preview only and do not perform any rollback."
        )
        self._submit_text(prompt, force_agent=True, clear_input=False)

    def _restore_selected_rollback(self) -> None:
        rollback_id = self._selected_rollback_id
        if rollback_id is None:
            return
        prompt = (
            f"Call the rollback_change tool with rollback_id={int(rollback_id)}. "
            "Restore that version and then tell me the result."
        )
        self._submit_text(prompt, force_agent=True, clear_input=False)

    def _build_empty_state(self) -> QFrame:
        card = QFrame()
        card.setFixedWidth(600)
        card.setStyleSheet(
            "background: rgba(15, 23, 42, 0.94); "
            f"border: 1px solid {C_BORDER}; border-radius: 24px;"
        )

        v = QVBoxLayout(card)
        v.setContentsMargins(28, 26, 28, 22)
        v.setSpacing(14)

        badge = QLabel("K")
        badge.setFixedSize(58, 58)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}); "
            "color: #fff; border-radius: 18px; font-size: 26px; font-weight: 800;"
        )
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        v.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("kagent")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 28px; font-weight: 800;")
        v.addWidget(title)

        subtitle = QLabel("像正式产品一样的聊天界面，支持流式回复、Markdown 渲染和 Agent 工具。")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 14px; line-height: 1.5;")
        v.addWidget(subtitle)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        chips.addStretch(1)
        for text, fg, bg, border in (
            ("流式回复", "#E9D5FF", "rgba(124, 58, 237, 0.14)", "rgba(124, 58, 237, 0.28)"),
            ("多轮对话", "#DBEAFE", "rgba(37, 99, 235, 0.14)", "rgba(37, 99, 235, 0.28)"),
            ("Agent 工具", "#BBF7D0", "rgba(34, 197, 94, 0.12)", "rgba(34, 197, 94, 0.26)"),
        ):
            chips.addWidget(_chip_label(text, fg, bg, border))
        chips.addStretch(1)
        v.addLayout(chips)

        hint = QLabel("Enter 发送 · Shift+Enter 换行")
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
            title = s["title"] or "新会话"
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            item.setToolTip(title)
            item.setSizeHint(QSize(0, 46))
            self.session_list.addItem(item)
            if s["id"] == self.current_session:
                self.session_list.setCurrentItem(item)
        self.session_list.blockSignals(False)
        self._update_status()

    def _current_session_title(self) -> str:
        item = self.session_list.currentItem()
        if item is not None:
            return item.text() or "新会话"
        if self.current_session:
            for s in db.list_sessions():
                if s["id"] == self.current_session:
                    return s["title"] or "新会话"
        return "新会话"

    def _open_session(self, session_id: str):
        if self._is_busy():
            QMessageBox.information(self, "kagent", "当前任务正在执行中，请先等待完成。")
            return

        self.current_session = session_id
        self._streaming_buf = ""
        self._streaming_time = ""
        self._activity = "就绪"
        self._send_locked = False
        self._reset_tool_trace()
        self._load_sessions()
        msgs = db.get_messages(session_id)
        self._render_messages(msgs)
        self._refresh_rollback_history_panel()
        self.input.setFocus()

    def new_session(self):
        if self._is_busy():
            QMessageBox.information(self, "kagent", "当前任务正在执行中，请先等待完成。")
            return

        sid = uuid.uuid4().hex[:12]
        db.create_session(sid)
        self._open_session(sid)

    def _delete_current_session(self):
        if self._is_busy():
            QMessageBox.information(self, "kagent", "当前任务正在执行中，暂时不能删除会话。")
            return
        if not self.current_session:
            return

        title = self._current_session_title()
        answer = QMessageBox.question(
            self,
            "删除会话",
            f"确定删除「{title}」吗？",
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
            self._activity = "就绪"
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
        if not self.agent_btn.isChecked():
            return None

        width = self._bubble_width("assistant", "")
        trace = ToolTraceCard(width)
        trace.approval_decided.connect(self._resolve_inline_approval)
        trace.action_requested.connect(self._handle_trace_action)
        trace.set_state("执行中", kind="active")

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
        call_id = str(event.get("call_id") or event.get("id") or "")
        if not call_id:
            return

        name = str(event.get("name") or "tool")
        round_idx = event.get("round")
        try:
            round_idx = int(round_idx) if round_idx is not None else None
        except (TypeError, ValueError):
            round_idx = None

        if event_type == "tool_preview":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            preview = str(event.get("preview") or "")
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status="预览",
                args=args,
                preview=preview,
                round_idx=round_idx,
                approval_pending=False,
            )
        elif event_type == "tool_start":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status="执行中",
                args=args,
                round_idx=round_idx,
                approval_pending=False,
            )
        elif event_type == "tool_approval_required":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            preview = str(event.get("preview") or "")
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status="预览",
                args=args,
                preview=preview,
                round_idx=round_idx,
                approval_pending=True,
            )
            trace.set_state("等待确认", kind="active")
        elif event_type == "tool_approval_decision":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            preview = str(event.get("preview") or "")
            approved = bool(event.get("approved", False))
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status="执行中" if approved else "失败",
                args=args,
                preview=preview,
                round_idx=round_idx,
                error=not approved,
                approval_pending=False,
            )
            trace.set_state("执行中" if approved else "失败", kind="active" if approved else "error")
        elif event_type == "tool_result":
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            result = event.get("result") if isinstance(event.get("result"), dict) else {}
            error = not bool(event.get("ok", True))
            trace.upsert_event(
                call_id=call_id,
                name=name,
                status="失败" if error else "成功",
                args=args,
                result=result,
                round_idx=round_idx,
                error=error,
                approval_pending=False,
            )
            if error:
                trace.set_state("失败", kind="error")

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

                if self.agent_btn.isChecked() and (
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
        worker = self.worker if isinstance(self.worker, AgentWorker) else None
        if worker is None or not call_id:
            return
        worker.resolve_approval(call_id, approved)

    def _handle_trace_action(self, action: object) -> None:
        payload = action if isinstance(action, dict) else {}
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return
        if self._is_busy():
            QMessageBox.information(self, "kagent", "当前任务还在执行，先等它完成再点这个操作。")
            return
        self._submit_text(prompt, force_agent=True, clear_input=False)

    def _on_tool_event(self, event: dict[str, Any]):
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

    # ==================== State ====================

    def _is_busy(self) -> bool:
        return self._send_locked or bool(self.worker and self.worker.isRunning())

    def _sync_send_button_style(self):
        if self._is_busy():
            self.send_btn.setStyleSheet(
                "background: rgba(148, 163, 184, 0.18); color: #64748B; "
                "border: none; border-radius: 14px; padding: 8px 18px; "
                "font-size: 13px; font-weight: 800;"
            )
        else:
            self.send_btn.setStyleSheet(
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}); "
                "color: #fff; border: none; border-radius: 14px; padding: 8px 18px; "
                "font-size: 13px; font-weight: 800;"
            )

    def _sync_stop_button_style(self):
        if self._is_busy():
            if self._stop_requested:
                self.stop_btn.setStyleSheet(
                    "background: rgba(148, 163, 184, 0.18); color: #94A3B8; "
                    "border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 14px; "
                    "padding: 8px 18px; font-size: 13px; font-weight: 800;"
                )
                self.stop_btn.setText("停止中")
            else:
                self.stop_btn.setStyleSheet(
                    "background: rgba(239, 68, 68, 0.14); color: #FCA5A5; "
                    "border: 1px solid rgba(248, 113, 113, 0.28); border-radius: 14px; "
                    "padding: 8px 18px; font-size: 13px; font-weight: 800;"
                )
                self.stop_btn.setText("停止")
        else:
            self.stop_btn.setStyleSheet(
                "background: rgba(255, 255, 255, 0.04); color: #64748B; "
                f"border: 1px solid {C_BORDER}; border-radius: 14px; "
                "padding: 8px 18px; font-size: 13px; font-weight: 800;"
            )
            self.stop_btn.setText("停止")

    def _sync_mode_button_style(self):
        if self.agent_btn.isChecked():
            self.agent_btn.setStyleSheet(
                "background: rgba(124, 58, 237, 0.18); color: #E9D5FF; "
                "border: 1px solid rgba(124, 58, 237, 0.42); border-radius: 12px; "
                "padding: 8px 12px; font-size: 12px; font-weight: 800;"
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
        self.agent_btn.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy and not self._stop_requested)
        self._sync_mode_button_style()
        self._sync_send_button_style()
        self._sync_stop_button_style()

    def _refresh_chat_header(self):
        title = self._current_session_title()
        mode = "Agent" if self.agent_btn.isChecked() else "Chat"
        count = len(db.get_messages(self.current_session)) if self.current_session else 0

        self.chat_title_label.setText(title)
        self.chat_subtitle_label.setText(f"{MODEL} · {mode} · {count} 条消息 · {self._activity}")

        if self.agent_btn.isChecked():
            self.chat_mode_chip.setText("Agent")
            self.chat_mode_chip.setStyleSheet(
                "background: rgba(124, 58, 237, 0.16); color: #E9D5FF; "
                "border: 1px solid rgba(124, 58, 237, 0.34); border-radius: 999px; "
                "padding: 4px 10px; font-size: 11px; font-weight: 700;"
            )
        else:
            self.chat_mode_chip.setText("Chat")
            self.chat_mode_chip.setStyleSheet(
                "background: rgba(37, 99, 235, 0.16); color: #DBEAFE; "
                "border: 1px solid rgba(37, 99, 235, 0.34); border-radius: 999px; "
                "padding: 4px 10px; font-size: 11px; font-weight: 700;"
            )

    def _update_status(self):
        count = len(db.get_messages(self.current_session)) if self.current_session else 0
        self.status_count.setText(f"共 {count} 条消息")

    # ==================== Send Flow ====================

    def _stopped_message_for_worker(self, worker: ChatWorker | AgentWorker | None) -> str:
        if isinstance(worker, AgentWorker):
            return "已停止执行。"
        return "已停止生成。"

    def _schedule_stream_flush(self) -> None:
        if self._stream_flush_pending:
            return
        self._stream_flush_pending = True
        QTimer.singleShot(STREAM_RENDER_INTERVAL_MS, self._flush_streaming_update)

    def _flush_streaming_update(self) -> None:
        self._stream_flush_pending = False
        if isinstance(self.worker, AgentWorker):
            return
        if self._streaming_buf == self._stream_last_painted:
            return

        card = getattr(self, "_streaming_card", None)
        row = getattr(self, "_streaming_row", None)
        if card is None:
            msgs = db.get_messages(self.current_session) if self.current_session else []
            self._render_messages(msgs, streaming_html=self._streaming_buf)
            self._stream_last_painted = self._streaming_buf
            return

        card.update_body(self._streaming_buf, streaming=True)
        self._stream_last_painted = self._streaming_buf
        if row is not None:
            scrollbar = self.chat_scroll.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _on_stop_clicked(self):
        if not self._is_busy() or self.worker is None or self._stop_requested:
            return

        self._stop_requested = True
        self._activity = "停止中"
        self.worker.stop()
        self._set_busy_controls(True)
        self._refresh_chat_header()

    def _finalize_stopped_worker(self, worker: ChatWorker | AgentWorker | None):
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
            trace.set_state("已停止", kind="active")

        self._activity = "已停止"
        self._send_locked = False
        self.worker = None
        self._stop_requested = False
        self._stream_flush_pending = False
        self._stream_last_painted = ""
        self._set_busy_controls(False)
        self._streaming_buf = ""
        self._streaming_time = ""
        self._streaming_card = None
        self._streaming_row = None
        self._refresh_chat_header()
        self._update_status()
        self._refresh_rollback_history_panel()
        self.input.setFocus()

    def _submit_text(self, text: str, force_agent: bool = False, clear_input: bool = False) -> None:
        if self._is_busy():
            return
        if not self.current_session:
            self.new_session()
        if not self.current_session:
            return

        normalized = str(text or "").strip()
        if not normalized:
            return

        if force_agent:
            self.agent_btn.setChecked(True)
        elif not self.agent_btn.isChecked() and _looks_like_agent_task(normalized):
            self.agent_btn.setChecked(True)
        use_agent = self.agent_btn.isChecked()

        self._stop_requested = False
        self._stream_flush_pending = False
        self._stream_last_painted = ""
        if clear_input:
            self.input.clear()
        self._streaming_buf = ""
        self._streaming_time = datetime.now().strftime("%H:%M")
        """
        self._activity = "鎵ц涓? if use_agent else "鎬濊€冧腑"
        self._reset_tool_trace()
        """
        self._activity = "Working" if use_agent else "Thinking"
        self._reset_tool_trace()
        self._send_locked = True
        self._set_busy_controls(True)

        db.save_message(self.current_session, "user", normalized)
        history = db.get_messages(self.current_session)
        self._render_messages(history, thinking=True)

        if use_agent:
            self.worker = AgentWorker(self.current_session, normalized, history)
        else:
            self.worker = ChatWorker(self.current_session, normalized, history)

        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.title_ready.connect(self._on_title)
        if isinstance(self.worker, AgentWorker):
            self.worker.tool_event.connect(self._on_tool_event)
        worker = self.worker
        QTimer.singleShot(
            THINKING_PLACEHOLDER_DELAY_MS,
            lambda current_worker=worker: self._start_worker(current_worker),
        )

    def on_send(self):
        if self._is_busy():
            return
        if not self.current_session:
            self.new_session()
        if not self.current_session:
            return

        text = self.input.toPlainText().strip()
        self._submit_text(text, clear_input=True)
        return
        if not text:
            return

        if not self.agent_btn.isChecked() and _looks_like_agent_task(text):
            self.agent_btn.setChecked(True)
        use_agent = self.agent_btn.isChecked()

        self._stop_requested = False
        self._stream_flush_pending = False
        self._stream_last_painted = ""
        self.input.clear()
        self._streaming_buf = ""
        self._streaming_time = datetime.now().strftime("%H:%M")
        self._activity = "执行中" if use_agent else "思考中"
        self._reset_tool_trace()
        self._send_locked = True
        self._set_busy_controls(True)

        db.save_message(self.current_session, "user", text)
        history = db.get_messages(self.current_session)
        self._render_messages(history, thinking=True)

        if use_agent:
            self.worker = AgentWorker(self.current_session, text, history)
        else:
            self.worker = ChatWorker(self.current_session, text, history)

        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.title_ready.connect(self._on_title)
        if isinstance(self.worker, AgentWorker):
            self.worker.tool_event.connect(self._on_tool_event)
        worker = self.worker
        QTimer.singleShot(
            THINKING_PLACEHOLDER_DELAY_MS,
            lambda current_worker=worker: self._start_worker(current_worker),
        )

    def _release_detached_worker(self, worker: ChatWorker | AgentWorker | None) -> None:
        if worker is None:
            return
        if worker in self._detached_workers:
            self._detached_workers.remove(worker)
            worker.deleteLater()

    def _track_detached_worker(self, worker: ChatWorker | AgentWorker | None) -> None:
        if worker is None or worker in self._detached_workers:
            return
        self._detached_workers.append(worker)

    def _attach_worker_signals(self, worker: ChatWorker | AgentWorker) -> None:
        worker.chunk.connect(
            lambda piece, current_worker=worker: self._on_chunk(current_worker, piece)
        )
        worker.done.connect(
            lambda full, current_worker=worker: self._on_done(current_worker, full)
        )
        worker.error.connect(
            lambda msg, current_worker=worker: self._on_error(current_worker, msg)
        )
        worker.title_ready.connect(self._on_title)
        if isinstance(worker, AgentWorker):
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

    def _force_finalize_stopping_worker(self, worker: ChatWorker | AgentWorker | None) -> None:
        if worker is None:
            return
        if self.worker is not worker or not self._stop_requested:
            return
        self._track_detached_worker(worker)
        self._finalize_stopped_worker(worker)

    def _on_tool_event(self, worker: ChatWorker | AgentWorker, event: dict[str, Any]):
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

    def _submit_text(self, text: str, force_agent: bool = False, clear_input: bool = False) -> None:
        if self._is_busy():
            return
        if not self.current_session:
            self.new_session()
        if not self.current_session:
            return

        normalized = str(text or "").strip()
        if not normalized:
            return

        if force_agent:
            self.agent_btn.setChecked(True)
        elif not self.agent_btn.isChecked() and _looks_like_agent_task(normalized):
            self.agent_btn.setChecked(True)
        use_agent = self.agent_btn.isChecked()

        self._stop_requested = False
        self._stream_flush_pending = False
        self._stream_last_painted = ""
        if clear_input:
            self.input.clear()
        self._streaming_buf = ""
        self._streaming_time = datetime.now().strftime("%H:%M")
        self._activity = "Working" if use_agent else "Thinking"
        self._reset_tool_trace()
        self._send_locked = True
        self._set_busy_controls(True)

        db.save_message(self.current_session, "user", normalized)
        history = db.get_messages(self.current_session)
        self._render_messages(history, thinking=True)

        if use_agent:
            worker: ChatWorker | AgentWorker = AgentWorker(self.current_session, normalized, history)
        else:
            worker = ChatWorker(self.current_session, normalized, history)
        self.worker = worker
        self._attach_worker_signals(worker)

        QTimer.singleShot(
            THINKING_PLACEHOLDER_DELAY_MS,
            lambda current_worker=worker: self._start_worker(current_worker),
        )

    def on_send(self):
        text = self.input.toPlainText().strip()
        self._submit_text(text, clear_input=True)

    def _start_worker(self, worker: ChatWorker | AgentWorker | None):
        if worker is None:
            return
        if self.worker is not worker:
            return
        if getattr(worker, "_stop", False):
            self._finalize_stopped_worker(worker)
            return
        worker.start()

    def _on_chunk(self, worker: ChatWorker | AgentWorker, piece: str):
        if worker is not self.worker or isinstance(worker, AgentWorker):
            return
        self._streaming_buf += piece
        self._schedule_stream_flush()

    def _on_done(self, worker: ChatWorker | AgentWorker, full: str):
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
        trace = self._agent_trace_card if self.agent_btn.isChecked() else None
        if trace is not None:
            trace.set_state("Stopped" if was_stopped else "Done", kind="active" if was_stopped else "done")
        self._send_locked = False
        self.worker = None
        self._stop_requested = False
        self._stream_flush_pending = False
        self._stream_last_painted = ""
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

    def _on_error(self, worker: ChatWorker | AgentWorker, msg: str):
        if worker is not self.worker:
            return
        if self._stop_requested:
            self._finalize_stopped_worker(worker)
            return

        msgs = db.get_messages(self.current_session) if self.current_session else []
        self._activity = "Ready"
        streaming_html = None
        if not isinstance(worker, AgentWorker) and self._streaming_buf:
            streaming_html = self._streaming_buf
        self._render_messages(msgs, streaming_html=streaming_html, error_text=msg)
        trace = self._agent_trace_card if self.agent_btn.isChecked() else None
        if trace is not None:
            trace.set_state("Failed", kind="error")
        self._send_locked = False
        self.worker = None
        self._stop_requested = False
        self._stream_flush_pending = False
        self._stream_last_painted = ""
        self._set_busy_controls(False)
        self._sync_send_button_style()
        self._streaming_buf = ""
        self._streaming_time = ""
        self._refresh_rollback_history_panel()
        self.input.setFocus()
        QMessageBox.warning(self, "kagent", f"调用失败：\n\n{msg}")

    def _on_title(self, title: str):
        self._load_sessions()
        self._refresh_chat_header()

    # ==================== Qt ====================

    def closeEvent(self, e):
        workers: list[ChatWorker | AgentWorker] = []
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
