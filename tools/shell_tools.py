"""
shell_tools.py — запуск команд и скриптов для агента.
PowerShell, CMD, Python, .bat, .ps1.
"""
import re
import subprocess
import pathlib

_DANGEROUS = [
    re.compile(r'\bformat\s+[a-z]:', re.I),
    re.compile(r'\b(rd|rmdir)\s+.*/s.*[a-z]:\\(windows|system32|program[\s_]files)', re.I),
    re.compile(r'remove-item\s+.*-recurse.*[a-z]:\\(windows|system32|program[\s_]files)', re.I),
    re.compile(r'\bdel\b.*/[sf].*[a-z]:\\(windows|system32)', re.I),
    # удаление корня диска целиком
    re.compile(r'remove-item\s+.*-recurse\s+[a-z]:\\?\s*($|["\s])', re.I),
    re.compile(r'\b(rd|rmdir)\s+/s\s+[a-z]:\\?\s*($|["\s])', re.I),
]


def _is_dangerous(command: str) -> bool:
    for pat in _DANGEROUS:
        if pat.search(command):
            return True
    return False


def run_command(
    command: str,
    shell: str = "powershell",
    timeout: int = 30,
    workdir: str | None = None,
) -> str:
    """Выполнить команду в PowerShell или CMD. Возвращает stdout + stderr."""
    if _is_dangerous(command):
        return "[Отказано] Команда заблокирована: затрагивает системные файлы"

    if shell == "powershell":
        cmd = ["powershell", "-NonInteractive", "-Command", command]
    else:
        cmd = ["cmd", "/c", command]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir or None,
            encoding="utf-8",
            errors="replace",
        )
        parts = []
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"[stderr]\n{result.stderr.strip()}")
        if result.returncode != 0:
            parts.append(f"[код выхода: {result.returncode}]")
        return "\n".join(parts) if parts else "[OK] Выполнено без вывода"
    except subprocess.TimeoutExpired:
        return f"[Таймаут] Команда выполнялась дольше {timeout}с и остановлена"
    except FileNotFoundError as e:
        return f"[Не найден] {e}"
    except Exception as e:
        return f"[Ошибка] {e}"


def run_script(
    path: str,
    args: list | None = None,
    timeout: int = 60,
) -> str:
    """Запустить скрипт: .py, .bat, .ps1. Возвращает stdout + stderr."""
    p = pathlib.Path(path)
    if not p.is_absolute():
        desktop = pathlib.Path.home() / "Desktop"
        from_desktop = (desktop / p).resolve()
        p = from_desktop if from_desktop.exists() else p.resolve()

    if not p.exists():
        return f"[Не найден] {path}"

    ext = p.suffix.lower()
    if ext == ".py":
        cmd = ["python", str(p)] + (args or [])
    elif ext == ".bat":
        cmd = ["cmd", "/c", str(p)] + (args or [])
    elif ext == ".ps1":
        cmd = ["powershell", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(p)] + (args or [])
    else:
        return f"[Не поддерживается] Расширение {ext!r}. Поддерживаются: .py, .bat, .ps1"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        parts = []
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"[stderr]\n{result.stderr.strip()}")
        if result.returncode != 0:
            parts.append(f"[код выхода: {result.returncode}]")
        return "\n".join(parts) if parts else "[OK] Скрипт выполнен без вывода"
    except subprocess.TimeoutExpired:
        return f"[Таймаут] Скрипт выполнялся дольше {timeout}с и остановлен"
    except Exception as e:
        return f"[Ошибка] {e}"


_DISPATCH = {
    "run_command": lambda a: run_command(**a),
    "run_script":  lambda a: run_script(**a),
}


def dispatch(name: str, args: dict) -> str:
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"[Неизвестный инструмент] {name}"
    try:
        return fn(args)
    except Exception as e:
        return f"[Ошибка выполнения {name}] {e}"


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Выполнить команду в PowerShell (по умолчанию) или CMD. "
                "Используй для системных операций, установки пакетов, проверки процессов и всего что требует терминала. "
                "Команды затрагивающие системные файлы Windows заблокированы."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Команда для выполнения",
                    },
                    "shell": {
                        "type": "string",
                        "enum": ["powershell", "cmd"],
                        "description": "Оболочка: powershell (по умолчанию) или cmd",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Таймаут в секундах (по умолчанию 30)",
                    },
                    "workdir": {
                        "type": "string",
                        "description": "Рабочая директория для команды (опционально)",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_script",
            "description": (
                "Запустить скрипт — Python (.py), batch (.bat) или PowerShell (.ps1). "
                "Возвращает вывод скрипта."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Путь к скрипту",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Аргументы командной строки (опционально)",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Таймаут в секундах (по умолчанию 60)",
                    },
                },
                "required": ["path"],
            },
        },
    },
]

SCHEMAS_RESPONSES = [
    {
        "type": "function",
        "name": s["function"]["name"],
        "description": s["function"]["description"],
        "parameters": s["function"]["parameters"],
    }
    for s in SCHEMAS
]
