"""
logger.py — logging setup.
File: agent.log in the project root.
On startup: trimmed to the last MAX_LINES lines, then a new session separator is appended.
"""

import logging
import os
from collections import deque
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
LOG_PATH  = os.path.join(_PROJECT_ROOT, "agent.log")
MAX_LINES = 300


class _TailFileHandler(logging.Handler):
    def __init__(self, path: str, max_lines: int):
        super().__init__()
        self._path = path
        self._max  = max_lines
        self._buf: deque[str] = deque(maxlen=max_lines)

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    self._buf.append(line.rstrip("\n"))

    def emit(self, record: logging.LogRecord) -> None:
        self._buf.append(self.format(record))
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                f.write("\n".join(self._buf) + "\n")
        except Exception:
            pass


_logger: logging.Logger | None = None


def setup_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LINES:
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_LINES:])

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = _TailFileHandler(LOG_PATH, MAX_LINES)
    handler.setFormatter(fmt)

    _logger = logging.getLogger("grok")
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    _logger.propagate = False

    session_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _logger.info(f"{'─' * 20} Session {session_start} {'─' * 20}")
    return _logger


def get_logger(name: str = "") -> logging.Logger:
    root = _logger or setup_logger()
    return root.getChild(name) if name else root
