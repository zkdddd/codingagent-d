from PyQt6.QtCore import QThread, pyqtSignal

from .. import db, llm


class ChatWorker(QThread):
    """后台线程：流式调用 LLM，逐 chunk 通过 signal 推送到主线程。"""

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
            db.save_message(self.session_id, "user", self.message)
            self.history.append({"role": "user", "content": self.message})

            if len(self.history) == 1:
                title = llm.generate_title(self.message)
                self.title_ready.emit(title)
                db.rename_session(self.session_id, title)

            full = ""
            for piece in llm.stream_chat(self.history):
                if self._stop:
                    break
                full += piece
                self.chunk.emit(piece)

            if full:
                db.save_message(self.session_id, "assistant", full)
            self.done.emit(full)
        except Exception as e:
            self.error.emit(str(e))
