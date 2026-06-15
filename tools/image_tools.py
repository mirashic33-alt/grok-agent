"""image_tools.py — генерация картинок и скриншоты экрана."""

import json
import pathlib
from datetime import datetime

_ROOT = pathlib.Path(__file__).parent.parent
IMG_DIR = _ROOT / "workspace" / "img"


def _img_path(prefix: str, ext: str = "jpg") -> pathlib.Path:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return IMG_DIR / f"{prefix}_{ts}.{ext}"


def generate_image(prompt: str) -> str:
    """Сгенерировать картинку через xAI Aurora. Вернуть JSON {"status", "path"}."""
    import base64
    import data.keystore as keystore
    from openai import OpenAI

    api_key = keystore.get("GROK_API_KEY")
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1",
        timeout=120.0,
    )
    resp = client.images.generate(
        model="grok-imagine-image-quality",
        prompt=prompt,
        n=1,
        size="1792x1024",
        response_format="b64_json",
    )
    b64_data = resp.data[0].b64_json
    img_bytes = base64.b64decode(b64_data)
    path = _img_path("gen", "jpg")
    path.write_bytes(img_bytes)
    return json.dumps({"status": "ok", "path": str(path)}, ensure_ascii=False)


def take_screenshot() -> str:
    """Сделать скриншот экрана. Вернуть JSON {"status", "path"}."""
    path = _img_path("screenshot", "png")
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(str(path), "PNG")
    except ImportError:
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                import mss.tools
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(path))
        except ImportError:
            return json.dumps({"error": "Установи Pillow или mss: pip install pillow"}, ensure_ascii=False)
    return json.dumps({"status": "ok", "path": str(path)}, ensure_ascii=False)


SCHEMAS_RESPONSES = [
    {
        "type": "function",
        "name": "generate_image",
        "description": (
            "Сгенерировать картинку по текстовому описанию через xAI Aurora. "
            "Картинка сохраняется в workspace/img/. "
            "Используй когда пользователь просит нарисовать, сгенерировать или создать изображение."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Детальное описание картинки на английском языке для лучшего результата",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "type": "function",
        "name": "take_screenshot",
        "description": (
            "Сделать скриншот текущего экрана пользователя. "
            "Скриншот сохраняется в workspace/img/ и передаётся тебе для анализа. "
            "Используй чтобы посмотреть что происходит на экране, проанализировать интерфейс или помочь с отладкой."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

_DISPATCH = {
    "generate_image": lambda a: generate_image(a["prompt"]),
    "take_screenshot": lambda a: take_screenshot(),
}


def dispatch(name: str, args: dict) -> str:
    try:
        return _DISPATCH[name](args)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
