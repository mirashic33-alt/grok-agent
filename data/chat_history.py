"""
chat_history.py — save and load chat history.
File: workspace/chat_history.json
Stores the last _limit() messages, rotates automatically.
"""

import json
import os
from datetime import datetime

def _limit() -> int:
    try:
        import data.config as cfg
        return int(cfg.get("history_limit") or 100)
    except Exception:
        return 100

HISTORY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "workspace", "chat_history.json"
)


def _ensure_dir():
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)


def load() -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[-_limit():]
    except Exception:
        pass
    return []


def append(role: str, text: str, elapsed: float = 0.0) -> list[dict]:
    messages = load()
    entry = {
        "role": role,
        "text": text,
        "ts": datetime.now().strftime("%H:%M"),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    if elapsed:
        entry["elapsed"] = round(elapsed, 1)
    messages.append(entry)
    if len(messages) > _limit():
        messages = messages[-_limit():]
    _save(messages)
    return messages


def clear() -> None:
    _ensure_dir()
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump([], f)


def _save(messages: list[dict]) -> None:
    _ensure_dir()
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
