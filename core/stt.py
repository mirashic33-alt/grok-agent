"""Vosk STT — загрузка модели и стриминговая транскрипция."""

import json
import zipfile
import threading
import urllib.request
from pathlib import Path

ROOT           = Path(__file__).parent.parent
MODEL_DIR      = ROOT / "models" / "vosk-model-small-ru"
MODEL_URL      = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
MODEL_ZIP_NAME = "vosk-model-small-ru-0.22"
SAMPLE_RATE    = 16000

_model = None
_lock  = threading.Lock()


def is_loaded() -> bool:
    return _model is not None


def is_downloaded() -> bool:
    return MODEL_DIR.exists()


def load(on_status=None, on_progress=None) -> bool:
    """Загрузить модель в память. Если не скачана — скачает сначала."""
    global _model
    with _lock:
        if _model is not None:
            return True
        try:
            if not MODEL_DIR.exists():
                if on_status:
                    on_status("Скачиваю модель Vosk (~45MB)...")
                _download(on_progress)
            if on_status:
                on_status("Загружаю модель Vosk...")
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)
            _model = Model(str(MODEL_DIR))
            if on_status:
                on_status("Vosk готов")
            return True
        except Exception as e:
            if on_status:
                on_status(f"Ошибка Vosk: {e}")
            return False


def _download(on_progress=None):
    (ROOT / "models").mkdir(parents=True, exist_ok=True)
    zip_path = ROOT / "models" / "_vosk_tmp.zip"

    def _hook(count, block_size, total_size):
        if total_size > 0 and on_progress:
            on_progress(min(int(count * block_size * 100 / total_size), 99))

    urllib.request.urlretrieve(MODEL_URL, zip_path, reporthook=_hook)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(ROOT / "models")
    zip_path.unlink()

    extracted = ROOT / "models" / MODEL_ZIP_NAME
    if extracted.exists() and not MODEL_DIR.exists():
        extracted.rename(MODEL_DIR)

    if on_progress:
        on_progress(-1)


def new_recognizer():
    """Создать KaldiRecognizer для стриминга. None если модель не загружена."""
    if _model is None:
        return None
    from vosk import KaldiRecognizer
    return KaldiRecognizer(_model, SAMPLE_RATE)


def partial_result(rec) -> str:
    return json.loads(rec.PartialResult()).get("partial", "").strip()


def final_result(rec) -> str:
    return json.loads(rec.FinalResult()).get("text", "").strip()


def feed(rec, chunk) -> tuple[bool, str]:
    """Подать чанк в распознаватель. Возвращает (завершена_фраза, текст)."""
    if rec.AcceptWaveform(chunk):
        text = json.loads(rec.Result()).get("text", "").strip()
        return True, text
    return False, partial_result(rec)
