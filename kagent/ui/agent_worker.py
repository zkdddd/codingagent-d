from PyQt6.QtCore import QThread, pyqtSignal

from .. import db, llm
from ..agent import CodeAgent


class AgentWorker(QThread):
    """后台线程：调用 coding agent，逐段输出工具执行与结果。"""

    chunk = pyqtSignal(str)
    tool_event = pyqtSignal(object)
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

    @staticmethod
    def _final_answer_from_report(report: str) -> str:
        marker = "### 结果\n\n"
        idx = report.rfind(marker)
        if idx != -1:
            text = report[idx + len(marker):].strip()
            if text:
                return text
        return report.strip()

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
                on_event=self.tool_event.emit,
                should_stop=lambda: self._stop,
            )
            answer = self._final_answer_from_report(report)

            if answer and not self._stop:
                db.save_message(self.session_id, "assistant", answer)
            self.done.emit(answer)
        except Exception as e:
            self.error.emit(str(e))
