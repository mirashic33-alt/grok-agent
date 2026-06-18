import os
import pathlib
import data.keystore as keystore
import data.logger as logger

_log = logger.get_logger("digest")

_ROOT     = pathlib.Path(__file__).parent.parent
_MEMORY   = _ROOT / "workspace" / "memory"
_DIGESTS  = _ROOT / "workspace" / "digests"

_PROMPT = (
    "Перед тобой полный лог одного рабочего дня — разговоры, задачи, решения. "
    "Сделай краткую выжимку: что обсуждали, что сделали, какие решения приняли, что важно помнить. "
    "Пиши коротко и по делу — это будет контекст для следующих сессий. "
    "Подробности кода не нужны, только суть."
)


def _client():
    from openai import OpenAI
    return OpenAI(
        api_key=keystore.get("GROK_API_KEY"),
        base_url="https://api.x.ai/v1",
        timeout=120.0,
    )


def ensure_digests():
    """Создать выжимки для дней у которых их ещё нет."""
    if not _MEMORY.is_dir():
        return
    _DIGESTS.mkdir(parents=True, exist_ok=True)

    for mem_file in sorted(_MEMORY.glob("*.md")):
        digest_file = _DIGESTS / mem_file.name
        if digest_file.exists():
            continue

        content = mem_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        _log.info(f"Creating digest for {mem_file.name}")
        try:
            import data.config as cfg
            model = cfg.get("digest_model") or "grok-3-mini"
            client = _client()
            resp = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": _PROMPT},
                    {"role": "user",   "content": content},
                ],
                store=False,
            )
            text = ""
            for item in resp.output:
                if getattr(item, "type", None) == "message":
                    for part in item.content:
                        if getattr(part, "type", None) == "output_text" and part.text:
                            text = part.text
                            break
            if text.strip():
                digest_file.write_text(text.strip(), encoding="utf-8")
                _log.info(f"Digest saved: {digest_file.name}")
            else:
                _log.warning(f"Empty digest for {mem_file.name}")
        except Exception as e:
            _log.error(f"Digest failed for {mem_file.name}: {e}")
