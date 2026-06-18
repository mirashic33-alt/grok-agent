"""
process_tools.py — управление процессами и окнами.

Инструменты:
  run_background   — запустить файл в фоне, вернуть PID
  stop_process     — остановить процесс по PID (graceful или force kill)
  list_processes   — список запущенных процессов с фильтром по имени
"""

import os
import sys
import subprocess
import pathlib

# Реестр процессов запущенных через run_background (PID → Popen)
_launched: dict[int, subprocess.Popen] = {}

_LAUNCH_BLOCKED = [
    os.environ.get("SystemRoot", "C:\\Windows"),
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
]


def _blocked(path: str) -> bool:
    p = os.path.abspath(path).lower()
    return any(p.startswith(b.lower()) for b in _LAUNCH_BLOCKED)


def _resolve(path: str) -> str:
    p = pathlib.Path(path)
    if not p.is_absolute():
        desktop = pathlib.Path.home() / "Desktop"
        candidate = (desktop / p).resolve()
        if candidate.exists():
            return str(candidate)
        return str(p.resolve())
    return str(p)


# ── run_background ─────────────────────────────────────────────────────────────

def run_background(path: str, args: str = "") -> str:
    """Запустить файл в фоне. Возвращает PID."""
    path = _resolve(path)
    if not os.path.exists(path):
        return f"[Не найден] {path}"
    if _blocked(path):
        return f"[Отказано] Системная папка: {path}"

    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        cmd = [sys.executable, path] + (args.split() if args else [])
    elif ext in (".bat", ".cmd"):
        cmd = ["cmd.exe", "/c", path] + (args.split() if args else [])
    elif ext == ".ps1":
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", path] + (args.split() if args else [])
    elif ext == ".exe":
        cmd = [path] + (args.split() if args else [])
    else:
        cmd = ["cmd.exe", "/c", "start", "", path]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(os.path.abspath(path)),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
        _launched[proc.pid] = proc
        return f"Запущено: {os.path.basename(path)} | PID={proc.pid}"
    except Exception as e:
        return f"[Ошибка запуска] {e}"


# ── stop_process ──────────────────────────────────────────────────────────────

def stop_process(pid: int, force: bool = False) -> str:
    """Остановить процесс по PID."""
    try:
        import psutil
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill() if force else proc.terminate()
        action = "принудительно завершён" if force else "завершён"
        _launched.pop(pid, None)
        return f"Процесс {pid} ({name}) {action}"
    except ImportError:
        pass
    except Exception as e:
        return f"[Ошибка] {e}"

    # Fallback — taskkill
    try:
        flag = "/F" if force else ""
        r = subprocess.run(
            f"taskkill {flag} /PID {pid}",
            shell=True, capture_output=True, text=True, timeout=5
        )
        _launched.pop(pid, None)
        return r.stdout.strip() or r.stderr.strip() or f"taskkill /PID {pid} выполнено"
    except Exception as e:
        return f"[Ошибка] {e}"


# ── list_processes ─────────────────────────────────────────────────────────────

def list_processes(name_filter: str = "") -> str:
    """Список запущенных процессов. Фильтр по имени — опционально."""
    try:
        import psutil
        rows = []
        for p in psutil.process_iter(["pid", "name", "status"]):
            try:
                info = p.info
                if name_filter and name_filter.lower() not in info["name"].lower():
                    continue
                rows.append(f"PID={info['pid']:<6}  {info['name']:<35}  {info['status']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if not rows:
            return "Процессов не найдено" + (f" по фильтру '{name_filter}'" if name_filter else "")
        return "\n".join(rows)
    except ImportError:
        pass

    # Fallback — tasklist
    try:
        cmd = f"tasklist /FI \"IMAGENAME eq *{name_filter}*\"" if name_filter else "tasklist"
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=10,
                           encoding="cp866", errors="replace")
        return r.stdout.strip()
    except Exception as e:
        return f"[Ошибка] {e}"


# ── Dispatch ───────────────────────────────────────────────────────────────────

_DISPATCH = {
    "run_background": lambda a: run_background(a["path"], a.get("args", "")),
    "stop_process":   lambda a: stop_process(a["pid"], a.get("force", False)),
    "list_processes": lambda a: list_processes(a.get("name_filter", "")),
}


def dispatch(name: str, args: dict) -> str:
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"[Неизвестный инструмент] {name}"
    try:
        return fn(args)
    except Exception as e:
        return f"[Ошибка {name}] {e}"


# ── Schemas (Responses API format) ────────────────────────────────────────────

SCHEMAS_RESPONSES = [
    {
        "type": "function",
        "name": "run_background",
        "description": (
            "Запустить файл в фоне (неблокирующий). "
            "Поддерживает: .py (запускается через текущий Python), .bat/.cmd, .exe, .ps1. "
            "Возвращает PID — сохрани его чтобы потом остановить через stop_process."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к файлу"},
                "args": {"type": "string", "description": "Аргументы командной строки (опционально)"},
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "stop_process",
        "description": (
            "Остановить процесс по PID. "
            "force=false — мягкое завершение (terminate). "
            "force=true — принудительное уничтожение (kill). "
            "Используй list_processes чтобы найти PID если не знаешь его."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pid":   {"type": "integer", "description": "PID процесса"},
                "force": {"type": "boolean", "description": "true = kill немедленно, false = graceful terminate"},
            },
            "required": ["pid"],
        },
    },
    {
        "type": "function",
        "name": "list_processes",
        "description": (
            "Список запущенных процессов. "
            "Опционально фильтр по части имени — например 'python', 'chrome', 'grok'. "
            "Возвращает PID, имя и статус каждого процесса."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name_filter": {"type": "string", "description": "Часть имени для фильтрации (опционально)"},
            },
            "required": [],
        },
    },
]
