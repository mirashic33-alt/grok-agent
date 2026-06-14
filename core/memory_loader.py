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

_WORKSPACE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "workspace",
)

_MEMORY_FILES = [
    ("agent.md",  "AGENT"),
    ("MEMORY.md", "MEMORY"),
    ("USER.md",   "USER"),
    ("SOUL.md",   "SOUL"),
    ("STYLE.md",  "STYLE"),
]


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
