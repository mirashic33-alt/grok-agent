import time
import data.logger as logger
import llm.provider as provider
from PySide6.QtCore import QThread, Signal

_log = logger.get_logger("worker")


class MessageWorker(QThread):
    finished   = Signal(str, float)   # text, elapsed seconds
    error      = Signal(str)
    tool_used  = Signal(str)          # tool label, e.g. "Поиск в интернете"

    def __init__(self, history: list[dict], model: str = "grok-4.3"):
        super().__init__()
        self._history = history
        self._model   = model

    def run(self):
        t0 = time.monotonic()
        try:
            def _on_tool(name: str, label: str):
                self.tool_used.emit(label)

            text    = provider.chat(self._history, self._model, on_tool_call=_on_tool)
            elapsed = time.monotonic() - t0
            _log.info(f"Reply in {elapsed:.1f}s")
            self.finished.emit(text, elapsed)
        except Exception as e:
            _log.error(f"LLM error: {e}")
            self.error.emit(str(e))
