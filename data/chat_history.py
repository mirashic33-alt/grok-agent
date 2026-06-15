"""
chat_history.py — save and load chat history.
File: workspace/chat_history.json
Stores the last _limit() messages, rotates automatically.
"""

import json
import os
import pathlib
from datetime import datetime

_ROOT = pathlib.Path(__file__).parent.parent

def _limit() -> int:
    try:
        import data.config as cfg
        return int(cfg.get("history_limit") or 100)
    except Exception:
        return 100

HISTORY_PATH = str(_ROOT / "workspace" / "chat_history.json")
IMG_DIR = _ROOT / "workspace" / "img"


def _ensure_dir():
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)


def save_image(image_bytes: bytes, ext: str = "jpg") -> str:
    """Сохранить картинку в workspace/img/, вернуть абсолютный путь."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    filename = f"{ts}.{ext}"
    path = IMG_DIR / filename
    path.write_bytes(image_bytes)
    return str(path)


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


def append(role: str, text: str, elapsed: float = 0.0, image_path: str = "") -> list[dict]:
    messages = load()
    entry = {
        "role": role,
        "text": text,
        "ts": datetime.now().strftime("%H:%M"),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    if elapsed:
        entry["elapsed"] = round(elapsed, 1)
    if image_path:
        entry["image_path"] = image_path
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
