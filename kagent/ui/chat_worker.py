import threading

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
        self._stream = None
        self._stream_lock = threading.Lock()

    def stop(self):
        self._stop = True
        self._close_stream()

    def _close_stream(self) -> None:
        with self._stream_lock:
            stream = self._stream
            self._stream = None
        if stream is None:
            return
        try:
            stream.close()
        except Exception:
            pass

    def _schedule_title_generation(self) -> None:
        if len(self.history) != 1:
            return

        def _run() -> None:
            title = llm.generate_title(self.message)
            if not title:
                return
            db.rename_session(self.session_id, title)
            self.title_ready.emit(title)

        threading.Thread(
            target=_run,
            name=f"kagent-title-{self.session_id}",
            daemon=True,
        ).start()

    def run(self):
        try:
            if self._stop:
                self.done.emit("")
                return

            # 标题生成放到独立线程，避免它阻塞首包显示和停止操作。
            self._schedule_title_generation()

            full = ""
            with self._stream_lock:
                if self._stop:
                    self.done.emit("")
                    return
                self._stream = llm.open_chat_stream(self.history)
                stream = self._stream

            try:
                for chunk in stream:
                    if self._stop:
                        break
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    content = delta.content if delta else None
                    if not content:
                        continue
                    full += content
                    self.chunk.emit(content)
            finally:
                self._close_stream()

            if full and not self._stop:
                db.save_message(self.session_id, "assistant", full)
            self.done.emit("" if self._stop else full)
        except Exception as e:
            if self._stop:
                self.done.emit("")
                return
            self.error.emit(str(e))
