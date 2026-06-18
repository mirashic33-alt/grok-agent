"""
file_tools.py — полный набор файловых операций для агента.
Доступ к любому пути на компьютере без ограничений.
"""
import shutil
import pathlib

_ROOT      = pathlib.Path(__file__).parent.parent
_WORKSPACE = _ROOT / "workspace"

_PROTECTED = [
    pathlib.Path("C:/Windows"),
    pathlib.Path("C:/Program Files"),
    pathlib.Path("C:/Program Files (x86)"),
    pathlib.Path("C:/ProgramData"),
]


def _is_protected(p: pathlib.Path) -> bool:
    try:
        resolved = p.resolve()
        for prot in _PROTECTED:
            try:
                resolved.relative_to(prot.resolve())
                return True
            except ValueError:
                pass
    except Exception:
        pass
    return False


def _p(path: str) -> pathlib.Path:
    """
    Нормализует путь.
    Абсолютный — используется как есть.
    Относительный — проверяем в порядке:
      1. от корня проекта (например 'workspace/SOUL.md')
      2. от рабочего стола пользователя
    """
    p = pathlib.Path(path)
    if p.is_absolute():
        return p.resolve()
    # сначала пробуем от корня проекта
    from_root = (_ROOT / p).resolve()
    if from_root.exists():
        return from_root
    # потом от рабочего стола
    desktop = pathlib.Path.home() / "Desktop"
    return (desktop / p).resolve()


# ── Чтение ───────────────────────────────────────────────────────────────────

def read_file(path: str, encoding: str = "utf-8") -> str:
    """Прочитать текстовый файл."""
    try:
        return _p(path).read_text(encoding=encoding, errors="replace")
    except FileNotFoundError:
        return f"[Не найден] {path}"
    except Exception as e:
        return f"[Ошибка чтения] {e}"


def read_file_lines(path: str, start: int = 1, end: int | None = None) -> str:
    """Прочитать диапазон строк файла (start и end включительно, нумерация с 1)."""
    try:
        lines = _p(path).read_text(encoding="utf-8", errors="replace").splitlines()
        s = max(0, start - 1)
        e = end if end is None else end
        chunk = lines[s:e]
        return "\n".join(f"{s+i+1}: {l}" for i, l in enumerate(chunk))
    except FileNotFoundError:
        return f"[Не найден] {path}"
    except Exception as e:
        return f"[Ошибка] {e}"


def get_file_info(path: str) -> str:
    """Информация о файле или папке: размер, дата изменения, тип."""
    try:
        p = _p(path)
        stat = p.stat()
        from datetime import datetime
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        kind = "папка" if p.is_dir() else "файл"
        size = stat.st_size
        size_str = f"{size} байт" if size < 1024 else f"{size/1024:.1f} KB" if size < 1024**2 else f"{size/1024**2:.1f} MB"
        return f"{kind}: {p}\nРазмер: {size_str}\nИзменён: {mtime}"
    except FileNotFoundError:
        return f"[Не найден] {path}"
    except Exception as e:
        return f"[Ошибка] {e}"


# ── Запись ───────────────────────────────────────────────────────────────────

def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """Создать новый файл или полностью перезаписать существующий."""
    try:
        p = _p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return f"[OK] Записан: {p}"
    except Exception as e:
        return f"[Ошибка записи] {e}"


def append_file(path: str, text: str) -> str:
    """Дописать текст в конец файла не трогая существующее содержимое."""
    try:
        p = _p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(text)
        return f"[OK] Дописано в: {p}"
    except Exception as e:
        return f"[Ошибка] {e}"


def insert_into_file(path: str, marker: str, text: str, after: bool = True) -> str:
    """Вставить текст до или после строки с маркером. Безопаснее write_file при точечных правках."""
    try:
        p = _p(path)
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        idx = next((i for i, l in enumerate(lines) if marker in l), None)
        if idx is None:
            return f"[Маркер не найден] {marker!r}"
        if not text.endswith("\n"):
            text += "\n"
        lines.insert(idx + 1 if after else idx, text)
        p.write_text("".join(lines), encoding="utf-8")
        return f"[OK] Вставлено {'после' if after else 'до'} строки {idx+1} в {p}"
    except FileNotFoundError:
        return f"[Не найден] {path}"
    except Exception as e:
        return f"[Ошибка] {e}"


def replace_in_file(path: str, old_text: str, new_text: str, count: int = 1) -> str:
    """Заменить вхождение текста в файле. count=-1 заменяет все вхождения."""
    try:
        p = _p(path)
        content = p.read_text(encoding="utf-8")
        if old_text not in content:
            return f"[Не найдено] текст {old_text!r} не встречается в файле"
        n = None if count == -1 else count
        new_content = content.replace(old_text, new_text, n if n is not None else -1)
        p.write_text(new_content, encoding="utf-8")
        replaced = content.count(old_text) if count == -1 else min(count, content.count(old_text))
        return f"[OK] Заменено {replaced} вхождений в {p}"
    except FileNotFoundError:
        return f"[Не найден] {path}"
    except Exception as e:
        return f"[Ошибка] {e}"


# ── Управление файлами ───────────────────────────────────────────────────────

def create_file(path: str) -> str:
    """Создать пустой файл (и все папки на пути если их нет)."""
    try:
        p = _p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            return f"[Уже существует] {p}"
        p.touch()
        return f"[OK] Создан: {p}"
    except Exception as e:
        return f"[Ошибка] {e}"


def delete_file(path: str) -> str:
    """Удалить файл."""
    try:
        p = _p(path)
        if _is_protected(p):
            return f"[Отказано] Путь защищён — удаление системных файлов запрещено: {p}"
        if not p.exists():
            return f"[Не найден] {path}"
        if p.is_dir():
            return f"[Ошибка] {path} — это папка, используй delete_directory"
        p.unlink()
        return f"[OK] Удалён: {p}"
    except Exception as e:
        return f"[Ошибка] {e}"


def move_to_trash(path: str) -> str:
    """Переместить файл или папку в корзину."""
    try:
        p = _p(path)
        if _is_protected(p):
            return f"[Отказано] Путь защищён: {p}"
        if not p.exists():
            return f"[Не найден] {path}"
        import send2trash
        send2trash.send2trash(str(p))
        return f"[OK] Перемещён в корзину: {p}"
    except ImportError:
        return "[Ошибка] Библиотека send2trash не установлена. Выполни: pip install send2trash"
    except Exception as e:
        return f"[Ошибка] {e}"


def rename_file(path: str, new_name: str) -> str:
    """Переименовать файл или папку. new_name — только имя, без пути."""
    try:
        p = _p(path)
        new_p = p.parent / new_name
        p.rename(new_p)
        return f"[OK] {p.name} → {new_p.name}"
    except FileNotFoundError:
        return f"[Не найден] {path}"
    except Exception as e:
        return f"[Ошибка] {e}"


def copy_file(src: str, dst: str) -> str:
    """Скопировать файл. dst — путь назначения (может включать новое имя)."""
    try:
        s = _p(src)
        d = _p(dst)
        if d.is_dir():
            d = d / s.name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(s), str(d))
        return f"[OK] Скопирован: {s} → {d}"
    except FileNotFoundError:
        return f"[Не найден] {src}"
    except Exception as e:
        return f"[Ошибка] {e}"


def move_file(src: str, dst: str) -> str:
    """Переместить файл или папку."""
    try:
        s = _p(src)
        d = _p(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        return f"[OK] Перемещён: {s} → {d}"
    except FileNotFoundError:
        return f"[Не найден] {src}"
    except Exception as e:
        return f"[Ошибка] {e}"


# ── Папки ────────────────────────────────────────────────────────────────────

def create_directory(path: str) -> str:
    """Создать папку (и все родительские если нужно)."""
    try:
        p = _p(path)
        p.mkdir(parents=True, exist_ok=True)
        return f"[OK] Папка создана: {p}"
    except Exception as e:
        return f"[Ошибка] {e}"


def delete_directory(path: str, recursive: bool = False) -> str:
    """Удалить папку. recursive=true — вместе со всем содержимым."""
    try:
        p = _p(path)
        if _is_protected(p):
            return f"[Отказано] Путь защищён — удаление системных папок запрещено: {p}"
        if not p.exists():
            return f"[Не найдено] {path}"
        if not p.is_dir():
            return f"[Ошибка] {path} — это файл, используй delete_file"
        if recursive:
            shutil.rmtree(str(p))
            return f"[OK] Папка удалена рекурсивно: {p}"
        else:
            p.rmdir()  # упадёт если не пустая
            return f"[OK] Папка удалена: {p}"
    except OSError as e:
        return f"[Ошибка] Папка не пустая или нет доступа: {e}"
    except Exception as e:
        return f"[Ошибка] {e}"


def list_files(directory: str, pattern: str = "*", recursive: bool = False) -> str:
    """
    Список файлов и папок в директории.
    pattern — glob-фильтр (например '*.md', '*.py').
    recursive=true — включая все подпапки.
    """
    try:
        p = _p(directory)
        if not p.is_dir():
            return f"[Не директория] {directory}"
        if recursive:
            items = sorted(p.rglob(pattern))
        else:
            items = sorted(p.glob(pattern))
        if not items:
            return f"[Пусто] нет файлов по шаблону {pattern!r}"
        lines = []
        for item in items:
            rel = str(item.relative_to(p))
            suffix = "/" if item.is_dir() else ""
            lines.append(f"{rel}{suffix}")
        return "\n".join(lines)
    except Exception as e:
        return f"[Ошибка] {e}"


def tree(directory: str = ".", max_depth: int = 3) -> str:
    """
    Дерево файлов и папок — как команда tree.
    Быстрый способ увидеть всю структуру одним вызовом.
    max_depth — глубина вложенности (по умолчанию 3).
    """
    try:
        root = _p(directory)
        if not root.is_dir():
            return f"[Не директория] {directory}"
        lines = [str(root) + "/"]

        def _walk(path: pathlib.Path, prefix: str, depth: int):
            if depth > max_depth:
                return
            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                lines.append(prefix + "└── [нет доступа]")
                return
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                suffix = "/" if item.is_dir() else ""
                lines.append(f"{prefix}{connector}{item.name}{suffix}")
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    _walk(item, prefix + extension, depth + 1)

        _walk(root, "", 1)
        return "\n".join(lines)
    except Exception as e:
        return f"[Ошибка] {e}"


# ── Поиск ────────────────────────────────────────────────────────────────────

def search_files(directory: str, pattern: str, recursive: bool = True) -> str:
    """Найти файлы по имени (glob-шаблон). Например pattern='*.py'."""
    try:
        p = _p(directory)
        method = p.rglob if recursive else p.glob
        results = sorted(method(pattern))
        if not results:
            return f"[Не найдено] файлов по шаблону {pattern!r}"
        return "\n".join(str(r) for r in results[:200])
    except Exception as e:
        return f"[Ошибка] {e}"


def search_in_files(directory: str, text: str, pattern: str = "*.txt", recursive: bool = True) -> str:
    """Найти файлы содержащие указанный текст. Возвращает путь и строку с совпадением."""
    try:
        p = _p(directory)
        method = p.rglob if recursive else p.glob
        found = []
        for file in method(pattern):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.splitlines(), 1):
                    if text.lower() in line.lower():
                        found.append(f"{file}:{i}: {line.strip()}")
                        if len(found) >= 50:
                            break
            except Exception:
                pass
            if len(found) >= 50:
                break
        if not found:
            return f"[Не найдено] текст {text!r} не встречается"
        return "\n".join(found)
    except Exception as e:
        return f"[Ошибка] {e}"


def get_drives() -> str:
    """Список доступных дисков на компьютере (Windows)."""
    import string
    drives = []
    for letter in string.ascii_uppercase:
        d = pathlib.Path(f"{letter}:\\")
        if d.exists():
            drives.append(str(d))
    return "\n".join(drives) if drives else "[Нет дисков]"


# ── Диспетчер ────────────────────────────────────────────────────────────────

_DISPATCH = {
    "read_file":          lambda a: read_file(**a),
    "read_file_lines":    lambda a: read_file_lines(**a),
    "get_file_info":      lambda a: get_file_info(**a),
    "write_file":         lambda a: write_file(**a),
    "append_file":        lambda a: append_file(**a),
    "insert_into_file":   lambda a: insert_into_file(**a),
    "replace_in_file":    lambda a: replace_in_file(**a),
    "create_file":        lambda a: create_file(**a),
    "delete_file":        lambda a: delete_file(**a),
    "move_to_trash":      lambda a: move_to_trash(**a),
    "rename_file":        lambda a: rename_file(**a),
    "copy_file":          lambda a: copy_file(**a),
    "move_file":          lambda a: move_file(**a),
    "create_directory":   lambda a: create_directory(**a),
    "delete_directory":   lambda a: delete_directory(**a),
    "list_files":         lambda a: list_files(**a),
    "search_files":       lambda a: search_files(**a),
    "search_in_files":    lambda a: search_in_files(**a),
    "get_drives":         lambda a: get_drives(),
    "tree":               lambda a: tree(**a),
}


def dispatch(name: str, args: dict) -> str:
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"[Неизвестный инструмент] {name}"
    try:
        return fn(args)
    except Exception as e:
        return f"[Ошибка выполнения {name}] {e}"


# ── JSON-схемы ───────────────────────────────────────────────────────────────

# Chat Completions формат (вложенный)
SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Прочитать содержимое текстового файла по пути.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Абсолютный путь к файлу или относительный от рабочего стола"},
                    "encoding": {"type": "string", "description": "Кодировка, по умолчанию utf-8"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file_lines",
            "description": "Прочитать определённые строки файла (например строки 10–50). Удобно для больших файлов.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":  {"type": "string", "description": "Путь к файлу"},
                    "start": {"type": "integer", "description": "Первая строка (нумерация с 1)"},
                    "end":   {"type": "integer", "description": "Последняя строка включительно. Если не указан — до конца файла"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Получить информацию о файле или папке: тип, размер, дата изменения.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к файлу или папке"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Создать новый файл или ПОЛНОСТЬЮ перезаписать существующий. Использовать только для создания нового файла или когда нужна полная замена содержимого. Для правок существующих файлов предпочитай insert_into_file или replace_in_file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Путь к файлу"},
                    "content": {"type": "string", "description": "Полное содержимое файла"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Дописать текст в конец файла не затрагивая существующее содержимое.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к файлу"},
                    "text": {"type": "string", "description": "Текст для добавления в конец"},
                },
                "required": ["path", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insert_into_file",
            "description": "Вставить текст точечно — до или после строки с указанным маркером. Безопасно для редактирования существующих файлов.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":   {"type": "string", "description": "Путь к файлу"},
                    "marker": {"type": "string", "description": "Строка-маркер, рядом с которой будет вставка"},
                    "text":   {"type": "string", "description": "Текст для вставки"},
                    "after":  {"type": "boolean", "description": "true = после маркера (по умолчанию), false = перед маркером"},
                },
                "required": ["path", "marker", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": "Найти и заменить текст в файле. Точечная замена без перезаписи всего файла.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":     {"type": "string", "description": "Путь к файлу"},
                    "old_text": {"type": "string", "description": "Текст для замены"},
                    "new_text": {"type": "string", "description": "Новый текст"},
                    "count":    {"type": "integer", "description": "Сколько вхождений заменить. 1 = первое (по умолчанию), -1 = все"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Создать пустой файл. Папки на пути создаются автоматически.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к новому файлу"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Удалить файл безвозвратно. Используй только если нужно именно уничтожить файл. Для удаления с возможностью восстановления используй move_to_trash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к файлу"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_to_trash",
            "description": "Переместить файл или папку в корзину. Предпочтительный способ удаления — файл можно восстановить.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к файлу или папке"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Переименовать файл или папку.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":     {"type": "string", "description": "Путь к файлу или папке"},
                    "new_name": {"type": "string", "description": "Новое имя (только имя, без пути)"},
                },
                "required": ["path", "new_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Скопировать файл в другое место.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Источник — путь к файлу"},
                    "dst": {"type": "string", "description": "Назначение — путь или папка"},
                },
                "required": ["src", "dst"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Переместить файл или папку в другое место.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Источник"},
                    "dst": {"type": "string", "description": "Назначение"},
                },
                "required": ["src", "dst"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Создать папку (и все родительские папки если нужно).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к новой папке"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_directory",
            "description": "Удалить папку. Для удаления вместе с содержимым укажи recursive=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":      {"type": "string", "description": "Путь к папке"},
                    "recursive": {"type": "boolean", "description": "true = удалить вместе со всем содержимым"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Список файлов и папок в директории.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Путь к директории"},
                    "pattern":   {"type": "string", "description": "Glob-фильтр, например '*.md', '*.py'. По умолчанию '*'"},
                    "recursive": {"type": "boolean", "description": "true = включая все подпапки"},
                },
                "required": ["directory"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Найти файлы по имени (glob-шаблон) в директории.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Директория для поиска"},
                    "pattern":   {"type": "string", "description": "Glob-шаблон имени файла, например '*.py', 'report*'"},
                    "recursive": {"type": "boolean", "description": "true = искать рекурсивно (по умолчанию)"},
                },
                "required": ["directory", "pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Найти файлы содержащие указанный текст. Возвращает путь и строку с совпадением.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Директория для поиска"},
                    "text":      {"type": "string", "description": "Текст для поиска"},
                    "pattern":   {"type": "string", "description": "Фильтр по типу файлов, например '*.py', '*.txt'. По умолчанию '*.txt'"},
                    "recursive": {"type": "boolean", "description": "true = искать рекурсивно (по умолчанию)"},
                },
                "required": ["directory", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_drives",
            "description": "Получить список всех доступных дисков на компьютере.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tree",
            "description": "Показать структуру папки в виде дерева. Лучший первый шаг для ориентации — одним вызовом видишь всю структуру папки с вложенностью.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Путь к папке. По умолчанию '.' — текущая директория агента (корень проекта)"},
                    "max_depth": {"type": "integer", "description": "Глубина вложенности (по умолчанию 3)"},
                },
                "required": [],
            },
        },
    },
]


# Responses API формат (плоский — без вложенного объекта 'function')
SCHEMAS_RESPONSES = [
    {
        "type": s["function"]["name"] and "function",
        "name": s["function"]["name"],
        "description": s["function"]["description"],
        "parameters": s["function"]["parameters"],
    }
    for s in SCHEMAS
]
