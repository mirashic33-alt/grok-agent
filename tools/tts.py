import re
import tempfile
import os
import requests
from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import data.keystore as keystore
import data.config as config
import data.logger as logger

_log = logger.get_logger("tts")
_ENDPOINT = "https://api.x.ai/v1/tts"

# Глобальный плеер — чтобы GC не убил раньше времени
_player: QMediaPlayer | None = None
_audio_output: QAudioOutput | None = None
_tmp_file: str | None = None


def shorten_urls(text: str, max_len: int = 70) -> str:
    """Обрезать длинные URL до max_len символов + '...'"""
    def _cut(m):
        url = m.group(0)
        return url if len(url) <= max_len else url[:max_len] + "..."
    return re.sub(r'https?://\S+', _cut, text)


def clean_for_tts(text: str) -> str:
    # Футер Telegram: (37.5с · 151,360 ток.)
    text = re.sub(r'\(\d+[\.,]\d+с\s*·\s*[\d,]+\s*ток\.\)', '', text)
    # URL
    text = re.sub(r'https?://\S+', '', text)
    # Markdown: заголовки, жирный, курсив, код
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'`{1,3}.*?`{1,3}', '', text, flags=re.DOTALL)
    # HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    # Строки-разделители --- или ===
    text = re.sub(r'^[-=]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Эмодзи
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\U00002600-\U000027BF]', '', text)
    # Лишние пробелы и пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def is_enabled() -> bool:
    return bool(config.get("tts_enabled"))


def synthesize(text: str, voice: str | None = None) -> bytes:
    if voice is None:
        voice = config.get("tts_voice") or "ara"
    api_key = keystore.get("GROK_API_KEY")
    resp = requests.post(
        _ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "text": text[:15000],
            "voice_id": voice,
            "language": "ru",
            "output_format": {
                "codec":       "mp3",
                "sample_rate": 24000,
                "bit_rate":    128000,
            },
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content


def play(audio_bytes: bytes, on_finished=None):
    global _player, _audio_output, _tmp_file

    if _tmp_file and os.path.exists(_tmp_file):
        try:
            os.unlink(_tmp_file)
        except Exception:
            pass

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.write(audio_bytes)
    tmp.close()
    _tmp_file = tmp.name

    _audio_output = QAudioOutput()
    _player = QMediaPlayer()
    _player.setAudioOutput(_audio_output)
    _player.setSource(QUrl.fromLocalFile(_tmp_file))

    if on_finished:
        def _on_state(state):
            if state == QMediaPlayer.PlaybackState.StoppedState:
                on_finished()
        _player.playbackStateChanged.connect(_on_state)

    _player.play()
    _log.info(f"Playing TTS from {_tmp_file}")


class TTSWorker(QThread):
    """Генерирует аудио в фоне, возвращает байты."""
    done  = Signal(bytes)
    error = Signal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        try:
            audio = synthesize(clean_for_tts(self._text))
            self.done.emit(audio)
        except Exception as e:
            _log.error(f"TTS error: {e}")
            self.error.emit(str(e))
