"""
daily_log.py — appends every message to workspace/memory/YYYY-MM-DD.md.

One file per day. Written automatically, no model involvement.
The model can read these files manually via read_file() when needed.
"""

import os
from datetime import datetime

_MEMORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "workspace", "memory",
)


def _today_path() -> str:
    return os.path.join(_MEMORY_DIR, datetime.now().strftime("%Y-%m-%d") + ".md")


def append_message(role: str, text: str) -> None:
    if not text or not text.strip():
        return
    try:
        os.makedirs(_MEMORY_DIR, exist_ok=True)
        ts    = datetime.now().strftime("%H:%M")
        label = "Вы" if role == "user" else "Грок"
        block = f"## [{ts}] {label}\n{text.strip()}\n\n---\n\n"
        with open(_today_path(), "a", encoding="utf-8") as f:
            f.write(block)
    except Exception:
        pass
