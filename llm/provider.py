from typing import Callable
import data.keystore as keystore
import data.logger as logger
import data.token_log as token_log
from core.memory_loader import build_system_prompt
from openai import OpenAI

_log = logger.get_logger("llm")

_TOOL_LABELS = {
    "web_search": "Поиск в интернете",
}


def _client() -> OpenAI:
    return OpenAI(
        api_key=keystore.get("GROK_API_KEY"),
        base_url="https://api.x.ai/v1",
    )


def chat(
    history: list[dict],
    model: str | None = None,
    web_search: bool | None = None,
    on_tool_call: Callable[[str, str], None] | None = None,
) -> str:
    import data.config as cfg
    if model is None:
        model = cfg.get("model") or "grok-4.3"
    if web_search is None:
        web_search = bool(cfg.get("web_search"))
    system = build_system_prompt()
    client = _client()

    # Responses API — поддерживает web_search
    if web_search:
        input_messages = []
        if system:
            input_messages.append({"role": "system", "content": system})
        for m in history:
            role = "user" if m["role"] == "user" else "assistant"
            input_messages.append({"role": role, "content": m["text"]})

        _log.debug(f"Sending {len(input_messages)} messages to {model} (web_search=True)")
        resp = client.responses.create(
            model=model,
            input=input_messages,
            tools=[{"type": "web_search"}],
        )
        text = ""
        for item in resp.output:
            item_type = getattr(item, "type", None)
            if item_type == "web_search_call":
                label = _TOOL_LABELS.get("web_search", "web_search")
                _log.info("tool: web_search")
                if on_tool_call:
                    on_tool_call("web_search", label)
            elif item_type == "message":
                for part in item.content:
                    if getattr(part, "type", None) == "output_text":
                        text = part.text
        usage = getattr(resp, "usage", None)
        if usage:
            in_t  = getattr(usage, "input_tokens",  0) or getattr(usage, "prompt_tokens",     0)
            out_t = getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0)
            token_log.record(in_t, out_t)
            _log.debug(f"Tokens: in={in_t} out={out_t}")
        _log.debug(f"Response: {len(text)} chars")
        return text

    # Chat Completions API — без поиска
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    for m in history:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["text"]})

    _log.debug(f"Sending {len(messages)} messages to {model} (web_search=False)")
    resp = client.chat.completions.create(model=model, messages=messages)
    text = resp.choices[0].message.content
    if resp.usage:
        token_log.record(resp.usage.prompt_tokens or 0, resp.usage.completion_tokens or 0)
        _log.debug(f"Tokens: in={resp.usage.prompt_tokens} out={resp.usage.completion_tokens}")
    _log.debug(f"Response: {len(text)} chars")
    return text
