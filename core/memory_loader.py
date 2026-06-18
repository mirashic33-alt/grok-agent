"""
memory_loader.py — loads workspace memory files into the system prompt.

Files loaded at every startup (in order):
  workspace/agent.md   — rules and behaviour
  workspace/MEMORY.md  — long-term facts (filled by agent)
  workspace/USER.md    — facts about the user (filled by agent)
  workspace/SOUL.md    — agent personality and name (filled by agent)
  workspace/STYLE.md   — manner of speaking (filled by agent)
  workspace/skills/*.md — agent skills, one file per skill
"""

import glob
import os
from tools.time_sense import get_time_block

_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE   = os.path.join(_ROOT, "workspace")
_DIGESTS_DIR = os.path.join(_WORKSPACE, "digests")

_MEMORY_FILES = [
    ("agent.md",  "AGENT"),
    ("MEMORY.md", "MEMORY"),
    ("USER.md",   "USER"),
    ("SOUL.md",   "SOUL"),
    ("STYLE.md",  "STYLE"),
]


def _load_digests() -> str:
    try:
        import data.config as cfg
        n = int(cfg.get("digests_count") or 0)
    except Exception:
        n = 2
    if n == 0 or not os.path.isdir(_DIGESTS_DIR):
        return ""
    files = sorted(f for f in os.listdir(_DIGESTS_DIR) if f.endswith(".md"))
    recent = files[-n:]
    parts = []
    for fname in recent:
        path = os.path.join(_DIGESTS_DIR, fname)
        try:
            content = open(path, encoding="utf-8").read().strip()
            if content:
                date = fname.replace(".md", "")
                parts.append(f"--- ДАЙДЖЕСТ {date} ---\n{content}")
        except Exception:
            pass
    return "\n\n".join(parts)


def ensure_workspace_files():
    """Создать пустые файлы личности при первом запуске если их нет."""
    os.makedirs(_WORKSPACE, exist_ok=True)
    os.makedirs(os.path.join(_WORKSPACE, "skills"), exist_ok=True)
    for filename, _ in _MEMORY_FILES:
        path = os.path.join(_WORKSPACE, filename)
        if not os.path.exists(path):
            open(path, "w", encoding="utf-8").close()


def _build_paths_block() -> str:
    import pathlib
    home = pathlib.Path.home()
    lines = [
        "Ты имеешь доступ ко всему компьютеру через файловые инструменты.",
        f"Домашняя папка пользователя: {home}",
        f"Рабочий стол: {home / 'Desktop'}",
        f"Корень твоего проекта (твои «кишки»): {_ROOT}",
        f"Workspace (твои файлы личности): {_WORKSPACE}",
        "Файлы личности:",
    ]
    for filename, _ in _MEMORY_FILES:
        path = os.path.join(_WORKSPACE, filename)
        mark = "✓" if os.path.exists(path) else "✗"
        lines.append(f"  {mark} {_WORKSPACE}\\{filename}")
    skills_dir = os.path.join(_WORKSPACE, "skills")
    if os.path.isdir(skills_dir):
        skill_files = sorted(f for f in os.listdir(skills_dir) if f.endswith(".md"))
        if skill_files:
            lines.append("Навыки:")
            for f in skill_files:
                lines.append(f"  ✓ {skills_dir}\\{f}")
    lines.append("Относительные пути в инструментах считаются от рабочего стола пользователя.")
    lines.append("Используй get_drives() чтобы увидеть все диски, list_files() чтобы исследовать любую папку.")
    return "\n".join(lines)


def _load_skills() -> str:
    skills_dir = os.path.join(_WORKSPACE, "skills")
    if not os.path.isdir(skills_dir):
        return ""
    parts = []
    for path in sorted(glob.glob(os.path.join(skills_dir, "*.md"))):
        try:
            content = open(path, encoding="utf-8").read().strip()
            if content:
                name = os.path.basename(path)
                parts.append(f"--- SKILL: {name} ---\n{content}")
        except Exception:
            pass
    return "\n\n".join(parts)


def build_system_prompt() -> str:
    sections: list[str] = []

    for filename, label in _MEMORY_FILES:
        path = os.path.join(_WORKSPACE, filename)
        if os.path.exists(path):
            try:
                content = open(path, encoding="utf-8").read().strip()
                if content:
                    sections.append(f"--- {label} ---\n{content}")
            except Exception as e:
                sections.append(f"--- {label} --- (load error: {e})")

    skills_block = _load_skills()
    if skills_block:
        sections.append(skills_block)

    digests_block = _load_digests()
    if digests_block:
        sections.append(digests_block)

    # Пути — модель должна точно знать где что лежит
    sections.append(_build_paths_block())

    # Время — всегда последним, всегда свежее
    try:
        import data.chat_history as _ch
        msgs = _ch.load()
        last = msgs[-1] if msgs else None
        time_block = get_time_block(
            last_message_ts=last.get("ts") if last else None,
            last_message_date=last.get("date") if last else None,
        )
    except Exception:
        time_block = get_time_block()
    sections.append(f"--- ВРЕМЯ ---\n{time_block}")

    return "\n\n".join(sections)
