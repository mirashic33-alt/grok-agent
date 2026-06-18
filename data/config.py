import json, pathlib

_PATH = pathlib.Path(__file__).parent / "config.json"

_DEFAULTS = {
    "model":         "grok-4.3",
    "theme":         "dark.json",
    "window_width":  715,
    "window_height": 825,
    "history_limit": 500,
    "web_search":    True,
    "tts_enabled":   False,
    "tts_voice":     "ara",
    "mic_enabled":   False,
    "digest_model":  "grok-3-mini",
    "digests_count": 2,
}


def load() -> dict:
    if _PATH.exists():
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
            return {**_DEFAULTS, **data}
        except Exception:
            pass
    return dict(_DEFAULTS)


def save(data: dict):
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def get(key: str):
    return load().get(key, _DEFAULTS.get(key))


def set(key: str, value):
    data = load()
    data[key] = value
    save(data)
