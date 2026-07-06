from PyQt6.QtCore import QThread, pyqtSignal

from .. import db, llm
from ..agent import CodeAgent


class AgentWorker(QThread):
    """后台线程：调用 coding agent，逐段输出工具执行与结果。"""

    chunk = pyqtSignal(str)
    done = pyqtSignal(str)
    error = pyqtSignal(str)
    title_ready = pyqtSignal(str)

    def __init__(self, session_id: str, message: str, history: list[dict]):
        super().__init__()
        self.session_id = session_id
        self.message = message
        self.history = history
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            if len(self.history) == 1:
                title = llm.generate_title(self.message)
                self.title_ready.emit(title)
                db.rename_session(self.session_id, title)

            agent = CodeAgent()
            report = agent.run(
                self.history,
                emit=self.chunk.emit,
                should_stop=lambda: self._stop,
            )

            if report and not self._stop:
                db.save_message(self.session_id, "assistant", report)
            self.done.emit(report)
        except Exception as e:
            self.error.emit(str(e))
