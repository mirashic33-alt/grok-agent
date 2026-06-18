import time
import data.logger as logger
import llm.provider as provider
from PySide6.QtCore import QThread, Signal

_log = logger.get_logger("worker")


class MessageWorker(QThread):
    finished      = Signal(str, float)   # text, elapsed seconds
    error         = Signal(str)
    tool_used     = Signal(str, str)     # (tool name, tool label)
    image_ready   = Signal(str)          # path to generated/screenshot image
    interim_text  = Signal(str)          # промежуточный текст между вызовами инструментов

    def __init__(self, history: list[dict], model: str = "grok-4.3", images: list | None = None):
        super().__init__()
        self._history = history
        self._model   = model
        self._images  = images or []

    def run(self):
        t0 = time.monotonic()
        try:
            def _on_tool(name: str, label: str):
                self.tool_used.emit(name, label)

            def _on_image(path: str):
                self.image_ready.emit(path)

            def _on_interim(text: str):
                self.interim_text.emit(text)

            text    = provider.chat(self._history, self._model, on_tool_call=_on_tool, images=self._images, on_image_ready=_on_image, on_interim_text=_on_interim)
            elapsed = time.monotonic() - t0
            _log.info(f"Reply in {elapsed:.1f}s")
            self.finished.emit(text, elapsed)
        except Exception as e:
            _log.error(f"LLM error: {e}")
            self.error.emit(str(e))
