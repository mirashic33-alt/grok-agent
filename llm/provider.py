import json
from typing import Callable
import data.keystore as keystore
import data.logger as logger
import data.token_log as token_log
from core.memory_loader import build_system_prompt
from openai import OpenAI
import tools.file_tools as file_tools
import tools.shell_tools as shell_tools
import tools.image_tools as image_tools

_log = logger.get_logger("llm")

_TOOL_LABELS = {
    "web_search":        "Поиск в интернете",
    "read_file":         "Читаю файл",
    "read_file_lines":   "Читаю строки файла",
    "get_file_info":     "Информация о файле",
    "write_file":        "Записываю файл",
    "append_file":       "Дописываю в файл",
    "insert_into_file":  "Редактирую файл",
    "replace_in_file":   "Заменяю текст в файле",
    "create_file":       "Создаю файл",
    "delete_file":       "Удаляю файл",
    "rename_file":       "Переименовываю",
    "copy_file":         "Копирую файл",
    "move_file":         "Перемещаю файл",
    "create_directory":  "Создаю папку",
    "delete_directory":  "Удаляю папку",
    "list_files":        "Просматриваю папку",
    "search_files":      "Ищу файлы",
    "search_in_files":   "Ищу текст в файлах",
    "get_drives":        "Смотрю диски",
    "tree":              "Смотрю структуру папки",
    "run_command":       "Выполняю команду",
    "run_script":        "Запускаю скрипт",
    "generate_image":    "Рисую картинку",
    "take_screenshot":   "Делаю скриншот",
}


def _compress_for_api(img_bytes: bytes, max_side: int = 1024, quality: int = 75) -> bytes:
    """Сжать картинку для отправки модели. Оригинал не трогаем."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception:
        return img_bytes  # fallback — отправляем как есть


def _make_label(name: str, args: dict) -> str:
    base = _TOOL_LABELS.get(name, name)
    key = args.get("path") or args.get("directory") or args.get("src") or ""
    return f"{base}: {key}" if key else base


def _client() -> OpenAI:
    return OpenAI(
        api_key=keystore.get("GROK_API_KEY"),
        base_url="https://api.x.ai/v1",
        timeout=300.0,
    )


def chat(
    history: list[dict],
    model: str | None = None,
    web_search: bool | None = None,
    on_tool_call: Callable[[str, str], None] | None = None,
    images: list | None = None,
    on_image_ready: Callable[[str], None] | None = None,
) -> str:
    import data.config as cfg
    if model is None:
        model = cfg.get("model") or "grok-4.3"
    if web_search is None:
        web_search = bool(cfg.get("web_search"))

    system = build_system_prompt()
    client = _client()

    # Собираем инструменты: file tools всегда, web_search по настройке
    tools = list(file_tools.SCHEMAS_RESPONSES) + list(shell_tools.SCHEMAS_RESPONSES) + list(image_tools.SCHEMAS_RESPONSES)
    if web_search:
        tools.insert(0, {"type": "web_search"})

    # Формируем входные сообщения
    input_msgs: list = []
    if system:
        input_msgs.append({"role": "system", "content": system})
    for m in history:
        role = "user" if m["role"] == "user" else "assistant"
        input_msgs.append({"role": role, "content": m["text"]})

    # Если пришли картинки — вставляем в последнее user-сообщение как multipart
    if images:
        import base64
        for i in range(len(input_msgs) - 1, -1, -1):
            if isinstance(input_msgs[i], dict) and input_msgs[i].get("role") == "user":
                txt = input_msgs[i]["content"] or "Что на этой картинке?"
                content = [{"type": "input_text", "text": txt}]
                for img_bytes in images:
                    small = _compress_for_api(img_bytes)
                    b64 = base64.b64encode(small).decode()
                    content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"})
                input_msgs[i] = {"role": "user", "content": content}
                break

    _log.debug(f"chat: {len(input_msgs)} msgs, model={model}, web_search={web_search}")

    in_tokens = out_tokens = 0
    MAX_TURNS = 8
    last_call: tuple | None = None
    repeat_count = 0
    final_text = ""

    for turn in range(MAX_TURNS):
        _log.info(f"tool loop turn {turn + 1}/{MAX_TURNS}")
        resp = client.responses.create(
            model=model,
            input=input_msgs,
            tools=tools,
            store=False,
        )

        usage = getattr(resp, "usage", None)
        if usage:
            in_tokens  += getattr(usage, "input_tokens",  0) or getattr(usage, "prompt_tokens",     0)
            out_tokens += getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0)

        has_tool_call = False

        for item in resp.output:
            itype = getattr(item, "type", None)
            input_msgs.append(item)  # возвращаем всё обратно для следующего turn

            if itype == "web_search_call":
                query = getattr(item, "query", "") or ""
                label = _TOOL_LABELS["web_search"]
                if query:
                    label = f"{label}: {query}"
                _log.info(f"tool: web_search({query!r})")
                if on_tool_call:
                    on_tool_call("web_search", label)

            elif itype == "function_call":
                has_tool_call = True
                name = item.name
                args = json.loads(getattr(item, "arguments", None) or "{}")
                call_id = getattr(item, "call_id", None)
                args_key = json.dumps(args, sort_keys=True)
                call_key = (name, args_key)

                # Детектор петли
                if call_key == last_call:
                    repeat_count += 1
                    if repeat_count >= 3:
                        _log.warning(f"Loop: {name} called 3x with same args")
                        token_log.record(in_tokens, out_tokens)
                        return "[Остановлено: повторяющийся вызов инструмента]"
                else:
                    last_call = call_key
                    repeat_count = 0

                label = _make_label(name, args)
                _log.info(f"tool: {name}({args})")
                if on_tool_call:
                    on_tool_call(name, label)

                if name in image_tools._DISPATCH:
                    result = image_tools.dispatch(name, args)
                elif name in shell_tools._DISPATCH:
                    result = shell_tools.dispatch(name, args)
                else:
                    result = file_tools.dispatch(name, args)
                _log.info(f"tool result [{name}]: {result[:300]}")

                input_msgs.append({
                    "type":    "function_call_output",
                    "call_id": call_id,
                    "output":  result,
                })

                # Уведомить UI о готовой картинке
                if name in ("generate_image", "take_screenshot"):
                    try:
                        r_data = json.loads(result)
                        img_path = r_data.get("path", "")
                        if img_path and on_image_ready:
                            on_image_ready(img_path)
                        # Для скриншота — передаём картинку модели для анализа
                        if name == "take_screenshot" and img_path:
                            import base64, pathlib as _pl
                            raw = _pl.Path(img_path).read_bytes()
                            small = _compress_for_api(raw)
                            b64 = base64.b64encode(small).decode()
                            input_msgs.append({
                                "role": "user",
                                "content": [
                                    {"type": "input_text", "text": "Вот скриншот экрана:"},
                                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"},
                                ],
                            })
                    except Exception:
                        pass

            elif itype == "message":
                for part in item.content:
                    if getattr(part, "type", None) == "output_text":
                        final_text = part.text

        if not has_tool_call:
            break

    token_log.record(in_tokens, out_tokens)
    _log.debug(f"Tokens: in={in_tokens} out={out_tokens} | Response: {len(final_text)} chars")
    return final_text
