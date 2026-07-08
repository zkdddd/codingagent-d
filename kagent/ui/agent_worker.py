import threading

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
        self._approval_lock = threading.Lock()
        self._approval_waiters: dict[str, dict[str, object]] = {}

    def stop(self):
        self._stop = True
        with self._approval_lock:
            waiters = list(self._approval_waiters.values())
        for waiter in waiters:
            event = waiter.get("event")
            if isinstance(event, threading.Event):
                event.set()

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
            name=f"kagent-agent-title-{self.session_id}",
            daemon=True,
        ).start()

    def resolve_approval(self, call_id: str, approved: bool) -> None:
        with self._approval_lock:
            waiter = self._approval_waiters.get(call_id)
            if waiter is None:
                return
            waiter["approved"] = bool(approved)
            event = waiter.get("event")
        if isinstance(event, threading.Event):
            event.set()

    @staticmethod
    def _final_answer_from_report(report: str) -> str:
        marker = "### 结果\n\n"
        idx = report.rfind(marker)
        if idx != -1:
            text = report[idx + len(marker):].strip()
            if text:
                return text
        if "已中止" in report:
            return ""
        return report.strip()

    def _confirm_tool(
        self,
        call_id: str,
        name: str,
        args: dict,
        preview: str | None,
        round_idx: int | None,
    ) -> bool:
        gate = threading.Event()
        with self._approval_lock:
            self._approval_waiters[call_id] = {"event": gate, "approved": None}

        self.tool_event.emit(
            {
                "type": "tool_approval_required",
                "call_id": call_id,
                "name": name,
                "args": args,
                "preview": preview,
                "round": round_idx,
            }
        )

        approved = False
        while not self._stop:
            if gate.wait(0.1):
                with self._approval_lock:
                    waiter = self._approval_waiters.get(call_id, {})
                    approved = bool(waiter.get("approved"))
                break

        with self._approval_lock:
            self._approval_waiters.pop(call_id, None)

        self.tool_event.emit(
            {
                "type": "tool_approval_decision",
                "call_id": call_id,
                "name": name,
                "args": args,
                "preview": preview,
                "round": round_idx,
                "approved": approved,
            }
        )
        return approved

    def run(self):
        try:
            if self._stop:
                self.done.emit("")
                return

            # 标题生成不阻塞 agent 首轮工具调用和停止操作。
            self._schedule_title_generation()

            agent = CodeAgent(
                confirm_tool=self._confirm_tool,
                session_id=self.session_id,
            )
            report = agent.run(
                self.history,
                emit=self.chunk.emit,
                on_event=self.tool_event.emit,
                should_stop=lambda: self._stop,
            )
            answer = "" if self._stop else self._final_answer_from_report(report)

            if answer and not self._stop:
                db.save_message(self.session_id, "assistant", answer)
            self.done.emit(answer)
        except Exception as e:
            if self._stop:
                self.done.emit("")
                return
            self.error.emit(str(e))
