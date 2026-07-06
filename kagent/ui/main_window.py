import html
import uuid
from datetime import datetime

from PyQt6.QtCore import Qt, QSize
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
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import db
from ..config import MODEL
from .agent_worker import AgentWorker
from .chat_worker import ChatWorker
from .markdown_view import highlight_css, render


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


def _assistant_body_html(content: str, streaming: bool, thinking: bool) -> str:
    if thinking:
        body = '<span class="typing">正在思考…</span>'
    else:
        body = render(content)
        if not body:
            body = '<span class="typing">准备回复…</span>'
    if streaming:
        body += '<span class="cursor">▍</span>'
    return body


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
        if streaming:
            body += '<span class="cursor">▍</span>'
        self.document().setDefaultStyleSheet(MESSAGE_BODY_STYLE)
        self.setHtml(f'<div style="color: {text_color};">{body}</div>')
        width = max(220, width)
        self.document().setTextWidth(width)
        self.document().adjustSize()
        height = int(self.document().size().height()) + 24
        self.setFixedSize(width, max(34, height))


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


class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("kagent")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        self.current_session: str | None = None
        self.worker: ChatWorker | AgentWorker | None = None
        self._streaming_buf = ""
        self._streaming_time = ""
        self._activity = "就绪"

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
        v.addWidget(self.chat_scroll, 1)

        v.addWidget(self._build_input_bar())
        return main

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
        self._sync_send_button_style()

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
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "kagent", "当前任务正在执行中，请先等待完成。")
            return

        self.current_session = session_id
        self._streaming_buf = ""
        self._streaming_time = ""
        self._activity = "就绪"
        self._load_sessions()
        msgs = db.get_messages(session_id)
        self._render_messages(msgs)
        self.input.setFocus()

    def new_session(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "kagent", "当前任务正在执行中，请先等待完成。")
            return

        sid = uuid.uuid4().hex[:12]
        db.create_session(sid)
        self._open_session(sid)

    def _delete_current_session(self):
        if self.worker and self.worker.isRunning():
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
            self._load_sessions()
            self._render_messages([])
            self.input.setFocus()

    def _on_session_clicked(self, item: QListWidgetItem):
        sid = item.data(Qt.ItemDataRole.UserRole)
        self._open_session(sid)

    # ==================== Render ====================

    def _clear_feed(self):
        _clear_layout(self.chat_layout)

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

    def _render_messages(
        self,
        msgs: list[dict],
        streaming_html: str | None = None,
        thinking: bool = False,
        error_text: str | None = None,
    ):
        self._streaming_card = None
        self._streaming_row = None
        self._clear_feed()

        last_widget: QWidget | None = None

        if not msgs and streaming_html is None and not thinking and error_text is None:
            self.chat_layout.addStretch(1)
            empty = self._build_empty_state()
            self.chat_layout.addWidget(empty, 0, Qt.AlignmentFlag.AlignHCenter)
            self.chat_layout.addStretch(1)
            last_widget = empty
        else:
            for m in msgs:
                row = self._build_message_row(
                    m["role"],
                    m["content"],
                    created_at=m.get("created_at"),
                )
                self.chat_layout.addWidget(row)
                last_widget = row

            if streaming_html is not None or thinking:
                row = self._build_message_row(
                    "assistant",
                    streaming_html or "",
                    created_at=self._streaming_time,
                    streaming=streaming_html is not None,
                    thinking=thinking,
                )
                self.chat_layout.addWidget(row)
                last_widget = row

            if error_text is not None:
                row = self._build_message_row(
                    "assistant",
                    error_text,
                    created_at=self._streaming_time,
                    error=True,
                )
                self.chat_layout.addWidget(row)
                last_widget = row

            self.chat_layout.addStretch(1)

        self.chat_content.adjustSize()
        if last_widget is not None:
            self.chat_scroll.ensureWidgetVisible(last_widget, 0, 24)
            self.chat_scroll.verticalScrollBar().setValue(self.chat_scroll.verticalScrollBar().maximum())

        self._refresh_chat_header()
        self._update_status()

    # ==================== State ====================

    def _is_busy(self) -> bool:
        return bool(self.worker and self.worker.isRunning())

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
        self._sync_mode_button_style()
        self._sync_send_button_style()

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

    def on_send(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.current_session:
            self.new_session()
        if not self.current_session:
            return

        text = self.input.toPlainText().strip()
        if not text:
            return

        self.input.clear()
        self._streaming_buf = ""
        self._streaming_time = datetime.now().strftime("%H:%M")
        self._activity = "执行中" if self.agent_btn.isChecked() else "思考中"
        self._set_busy_controls(True)

        db.save_message(self.current_session, "user", text)
        history = db.get_messages(self.current_session)
        self._render_messages(history, thinking=True)

        if self.agent_btn.isChecked():
            self.worker = AgentWorker(self.current_session, text, history)
        else:
            self.worker = ChatWorker(self.current_session, text, history)

        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.title_ready.connect(self._on_title)
        self.worker.start()

    def _on_chunk(self, piece: str):
        self._streaming_buf += piece
        card = getattr(self, "_streaming_card", None)
        row = getattr(self, "_streaming_row", None)
        if card is None:
            msgs = db.get_messages(self.current_session) if self.current_session else []
            self._render_messages(msgs, streaming_html=render(self._streaming_buf))
            return
        card.update_body(self._streaming_buf, streaming=True)
        if row is not None:
            self.chat_scroll.ensureWidgetVisible(row, 0, 24)
            self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            )

    def _on_done(self, full: str):
        card = getattr(self, "_streaming_card", None)
        row = getattr(self, "_streaming_row", None)
        self._activity = "就绪"
        if card is not None:
            card.update_body(full, streaming=False)
            if row is not None:
                self.chat_scroll.ensureWidgetVisible(row, 0, 24)
                self.chat_scroll.verticalScrollBar().setValue(
                    self.chat_scroll.verticalScrollBar().maximum()
                )
        else:
            msgs = db.get_messages(self.current_session) if self.current_session else []
            self._render_messages(msgs)
        self.worker = None
        self._set_busy_controls(False)
        self._sync_send_button_style()
        self._streaming_buf = ""
        self._streaming_time = ""
        self._streaming_card = None
        self._streaming_row = None
        self._refresh_chat_header()
        self._update_status()
        self.input.setFocus()

    def _on_error(self, msg: str):
        msgs = db.get_messages(self.current_session) if self.current_session else []
        self._activity = "就绪"
        streaming_html = render(self._streaming_buf) if self._streaming_buf else None
        self._render_messages(msgs, streaming_html=streaming_html, error_text=msg)
        self.worker = None
        self._set_busy_controls(False)
        self._sync_send_button_style()
        self._streaming_buf = ""
        self._streaming_time = ""
        self.input.setFocus()
        QMessageBox.warning(self, "kagent", f"调用失败：\n\n{msg}")

    def _on_title(self, title: str):
        self._load_sessions()
        self._refresh_chat_header()

    # ==================== Qt ====================

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        super().closeEvent(e)
