import html
import uuid

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeyEvent, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import db
from .chat_worker import ChatWorker
from .markdown_view import highlight_css, render

STYLE = """
QWidget#root { background: #f7f7f8; }
QListWidget#sidebar { background: #202123; color: #c5c5d0; border: none; outline: none; }
QListWidget#sidebar::item { padding: 10px 12px; border-radius: 6px; }
QListWidget#sidebar::item:hover { background: #2a2b2d; }
QListWidget#sidebar::item:selected { background: #343541; color: #fff; }
QPushButton#newBtn { background: transparent; color: #fff; border: 1px solid #565869;
    border-radius: 6px; padding: 8px; font-size: 13px; }
QPushButton#newBtn:hover { background: #2a2b2d; }
QTextEdit#input { background: #fff; border: 1px solid #d9d9e3; border-radius: 10px;
    padding: 8px 10px; font-size: 14px; }
QTextEdit#input:focus { border: 1px solid #10a37f; }
QPushButton#sendBtn { background: #10a37f; color: #fff; border: none; border-radius: 8px;
    padding: 8px 16px; font-size: 13px; font-weight: 600; }
QPushButton#sendBtn:disabled { background: #d9d9e3; }
QTextBrowser#chat { background: #ffffff; border: none; }
"""

CSS = """
.msg { margin: 0 24px 24px; padding: 14px 18px; border-radius: 10px; }
.msg.user { background: #f4f4f6; }
.msg.assistant { background: transparent; }
.role { font-size: 12px; color: #888; font-weight: 600; margin-bottom: 6px; }
.content { font-size: 14.5px; line-height: 1.75; color: #1a1a1a; }
pre { background: #1e1e2e; color: #cdd6f4; padding: 12px 14px; border-radius: 8px;
      overflow-x: auto; font-family: Consolas, Menlo, monospace; font-size: 13px; }
code { font-family: Consolas, Menlo, monospace; }
:not(pre) > code { background: #f0f0f3; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.cursor { color: #10a37f; }
"""

EMPTY_HTML = (
    '<div style="text-align:center; padding:120px 24px 40px;">'
    '<div style="font-size:28px; font-weight:600; color:#1a1a1a; margin-bottom:6px;">kagent</div>'
    '<div style="font-size:14px; color:#888;">开始一段新对话</div></div>'
)


class InputBox(QTextEdit):
    def __init__(self, on_send):
        super().__init__()
        self.setObjectName("input")
        self.setPlaceholderText("输入消息... (Enter 发送 / Shift+Enter 换行)")
        self.setFixedHeight(60)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.on_send = on_send

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            e.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.on_send()
            return
        super().keyPressEvent(e)


class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("kagent")
        self.resize(1100, 720)
        self.setStyleSheet(STYLE)

        self.current_session: str | None = None
        self.worker: ChatWorker | None = None
        self._streaming_buf = ""

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(0)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter)

        # 左侧栏
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background: #202123;")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(8, 12, 8, 8)
        sb_layout.setSpacing(8)

        new_btn = QPushButton("+ 新对话")
        new_btn.setObjectName("newBtn")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self.new_session)
        sb_layout.addWidget(new_btn)

        self.session_list = QListWidget()
        self.session_list.setObjectName("sidebar")
        self.session_list.itemClicked.connect(self._on_session_clicked)
        sb_layout.addWidget(self.session_list, 1)

        # 右侧主区
        main = QFrame()
        main.setStyleSheet("background: #ffffff;")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.chat = QTextBrowser()
        self.chat.setObjectName("chat")
        self.chat.setOpenExternalLinks(True)
        self.chat.setFont(QFont("Microsoft YaHei", 10))
        self.chat.document().setDefaultStyleSheet(highlight_css())
        self.chat.setHtml(EMPTY_HTML)
        main_layout.addWidget(self.chat, 1)

        # 输入区
        input_bar = QFrame()
        input_bar.setStyleSheet("background: #f7f7f8; border-top: 1px solid #e5e5e5;")
        ib_layout = QHBoxLayout(input_bar)
        ib_layout.setContentsMargins(16, 12, 16, 16)

        self.input = InputBox(self.on_send)
        ib_layout.addWidget(self.input, 1)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.on_send)
        ib_layout.addWidget(self.send_btn)

        main_layout.addWidget(input_bar)

        splitter.addWidget(sidebar)
        splitter.addWidget(main)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self._load_sessions()

    # ---------- 会话管理 ----------

    def _load_sessions(self):
        self.session_list.clear()
        for s in db.list_sessions():
            item = QListWidgetItem(s["title"] or "新对话")
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            if s["id"] == self.current_session:
                self.session_list.setCurrentItem(item)
            self.session_list.addItem(item)

    def new_session(self):
        sid = uuid.uuid4().hex[:12]
        db.create_session(sid)
        self.current_session = sid
        self._streaming_buf = ""
        self.chat.setHtml(EMPTY_HTML)
        self._load_sessions()
        self.input.setFocus()

    def _on_session_clicked(self, item: QListWidgetItem):
        sid = item.data(Qt.ItemDataRole.UserRole)
        self.current_session = sid
        self._streaming_buf = ""
        msgs = db.get_messages(sid)
        if not msgs:
            self.chat.setHtml(EMPTY_HTML)
            return
        self._render_messages(msgs, streaming_html=None)
        self.chat.moveCursor(QTextCursor.MoveOperation.End)

    def _render_messages(self, msgs: list[dict], streaming_html: str | None = None):
        parts = [f"<style>{CSS}</style>"]
        for m in msgs:
            role = "你" if m["role"] == "user" else "kagent"
            cls = m["role"]
            if m["role"] == "assistant":
                body = render(m["content"])
            else:
                body = html.escape(m["content"]).replace("\n", "<br>")
            parts.append(
                f'<div class="msg {cls}"><div class="role">{role}</div>'
                f'<div class="content">{body}</div></div>'
            )
        if streaming_html is not None:
            parts.append(
                '<div class="msg assistant"><div class="role">kagent</div>'
                f'<div class="content">{streaming_html}<span class="cursor">▍</span></div></div>'
            )
        self.chat.setHtml("".join(parts))
        self.chat.moveCursor(QTextCursor.MoveOperation.End)

    # ---------- 发送 ----------

    def on_send(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.current_session:
            self.new_session()
        text = self.input.toPlainText().strip()
        if not text:
            return

        self.input.clear()
        self._streaming_buf = ""

        history = db.get_messages(self.current_session)
        self._render_messages(history, streaming_html="")
        history_for_worker = db.get_messages(self.current_session)

        self.worker = ChatWorker(self.current_session, text, history_for_worker)
        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.title_ready.connect(self._on_title)
        self.send_btn.setEnabled(False)
        self.send_btn.setText("生成中…")
        self.worker.start()

    def _on_chunk(self, piece: str):
        self._streaming_buf += piece
        # 取已保存消息 + 当前流式块
        msgs = db.get_messages(self.current_session) if self.current_session else []
        self._render_messages(msgs, streaming_html=render(self._streaming_buf))

    def _on_done(self, full: str):
        msgs = db.get_messages(self.current_session) if self.current_session else []
        self._render_messages(msgs, streaming_html=None)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self._streaming_buf = ""

    def _on_error(self, msg: str):
        self._streaming_buf = ""
        self.chat.append(
            f'<div class="msg assistant"><div class="content" style="color:#e74c3c">'
            f'错误：{html.escape(msg)}</div></div>'
        )
        self.chat.moveCursor(QTextCursor.MoveOperation.End)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        QMessageBox.warning(self, "kagent", f"调用失败：\n\n{msg}")

    def _on_title(self, title: str):
        self._load_sessions()

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        super().closeEvent(e)
