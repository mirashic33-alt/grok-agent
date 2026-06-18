import threading
import requests as _req
from PySide6.QtCore import QThread, Signal
import data.logger as logger
import data.keystore as keystore

_log = logger.get_logger("telegram")
_API = "https://api.telegram.org/bot{token}/{method}"

_TOOL_EMOJI = {
    "web_search":        "🌐",
    "read_file":         "📖",
    "read_file_lines":   "📖",
    "get_file_info":     "ℹ️",
    "write_file":        "💾",
    "append_file":       "📝",
    "insert_into_file":  "✏️",
    "replace_in_file":   "✏️",
    "create_file":       "📄",
    "delete_file":       "🗑",
    "rename_file":       "🔤",
    "copy_file":         "📋",
    "move_file":         "📦",
    "create_directory":  "📁",
    "delete_directory":  "🗑",
    "list_files":        "📂",
    "search_files":      "🔍",
    "search_in_files":   "🔍",
    "get_drives":        "💽",
    "tree":              "🌳",
    "run_command":       "⚡",
    "run_script":        "▶️",
    "move_to_trash":     "🗑",
    "run_background":    "🚀",
    "stop_process":      "🛑",
    "list_processes":    "📋",
}


class TelegramBot(QThread):
    message_received = Signal(str)         # входящий текст от пользователя
    image_received   = Signal(str, bytes)  # (caption, image_bytes)
    clear_requested  = Signal()            # команда /clear из Telegram

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token    = keystore.get("TELEGRAM_TOKEN") or ""
        self._chat_id  = str(keystore.get("TELEGRAM_CHAT_ID") or "")
        self._offset   = 0
        self._running  = False
        self._session  = _req.Session()
        self._stop_typing = threading.Event()
        self._last_response = ""

    # ── отправка ─────────────────────────────────────────────────────────────

    def send(self, text: str):
        if not self._ready():
            return
        import data.config as _config
        import tools.tts as _tts
        self._last_response = text  # оригинал для TTS
        body = {"chat_id": self._chat_id, "text": _tts.shorten_urls(text)}
        if _config.get("tts_enabled"):
            body["reply_markup"] = {"inline_keyboard": [[
                {"text": "🔊 Озвучить", "callback_data": "speak"}
            ]]}
        try:
            self._session.post(self._url("sendMessage"), json=body, timeout=10)
        except Exception as e:
            _log.error(f"send error: {e}")

    def send_audio(self, audio_bytes: bytes):
        if not self._ready():
            return
        try:
            self._session.post(
                self._url("sendAudio"),
                data={"chat_id": self._chat_id, "title": "Луна", "performer": "Луна"},
                files={"audio": ("luna.mp3", audio_bytes, "audio/mpeg")},
                timeout=60,
            )
        except Exception as e:
            _log.error(f"send_audio error: {e}")

    def send_image(self, image_bytes: bytes, caption: str = ""):
        if not self._ready():
            return
        try:
            data = {"chat_id": self._chat_id}
            if caption:
                data["caption"] = caption
            self._session.post(
                self._url("sendPhoto"),
                data=data,
                files={"photo": ("image.jpg", image_bytes, "image/jpeg")},
                timeout=30,
            )
        except Exception as e:
            _log.error(f"send_image error: {e}")

    def _handle_speak_callback(self, callback_id: str):
        try:
            self._session.post(
                self._url("answerCallbackQuery"),
                json={"callback_query_id": callback_id, "text": "Озвучиваю..."},
                timeout=5,
            )
        except Exception:
            pass
        text = self._last_response
        if not text:
            return
        def _do():
            try:
                import tools.tts as tts
                audio = tts.synthesize(tts.clean_for_tts(text))
                self.send_audio(audio)
            except Exception as e:
                _log.error(f"TTS callback error: {e}")
        threading.Thread(target=_do, daemon=True).start()

    def send_tool(self, name: str, label: str):
        """Отправить курсивный индикатор вызова инструмента."""
        if not self._ready():
            return
        emoji = _TOOL_EMOJI.get(name, "⚙️")
        try:
            self._session.post(
                self._url("sendMessage"),
                json={
                    "chat_id": self._chat_id,
                    "text": f"<i>{emoji} {label}...</i>",
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
        except Exception as e:
            _log.error(f"send_tool error: {e}")

    def start_typing(self):
        self._stop_typing.clear()
        threading.Thread(target=self._typing_loop, daemon=True).start()

    def stop_typing(self):
        self._stop_typing.set()

    def _typing_loop(self):
        while not self._stop_typing.wait(timeout=4):
            if not self._ready():
                break
            try:
                self._session.post(
                    self._url("sendChatAction"),
                    json={"chat_id": self._chat_id, "action": "typing"},
                    timeout=5,
                )
            except Exception:
                pass

    # ── polling ──────────────────────────────────────────────────────────────

    def stop(self):
        self._running = False
        self._stop_typing.set()
        self._session.close()

    def _register_commands(self):
        commands = [
            {"command": "clear", "description": "Очистить историю чата"},
            {"command": "start", "description": "Статус агента"},
        ]
        try:
            self._session.post(
                self._url("setMyCommands"),
                json={"commands": commands},
                timeout=10,
            )
            _log.info("Commands registered")
        except Exception as e:
            _log.warning(f"setMyCommands error: {e}")

    def run(self):
        if not self._token:
            _log.warning("No Telegram token configured, bot disabled")
            return
        _log.info(f"Polling started, chat_id={self._chat_id}")
        self._register_commands()
        self._running = True
        while self._running:
            try:
                updates = self._get_updates()
                for upd in updates:
                    self._offset = upd["update_id"] + 1

                    # Inline кнопка "Озвучить"
                    cb = upd.get("callback_query")
                    if cb:
                        if cb.get("data") == "speak":
                            self._handle_speak_callback(cb["id"])
                        continue

                    msg = upd.get("message") or upd.get("edited_message")
                    if not msg:
                        continue
                    cid = str(msg["chat"]["id"])
                    text = msg.get("text", "").strip()

                    # Setup mode: chat_id не заполнен — говорим его пользователю
                    if not self._chat_id:
                        try:
                            self._session.post(
                                self._url("sendMessage"),
                                json={"chat_id": cid, "text": f"Твой chat_id: {cid}\n\nВставь его в Настройки → Ключи и перезапусти приложение."},
                                timeout=10,
                            )
                        except Exception:
                            pass
                        _log.info(f"Setup mode: told chat_id={cid}")
                        continue

                    # Проверка авторизации
                    if cid != self._chat_id:
                        _log.warning(f"Rejected message from chat_id={cid}")
                        continue

                    if text == "/start":
                        self.send("Агент онлайн. Пиши — отвечу.")
                        continue

                    if text == "/clear":
                        _log.info("← TG: /clear")
                        self.clear_requested.emit()
                        self.send("История чата очищена.")
                        continue

                    # Фото — проверяем до пустого текста
                    photo = msg.get("photo")
                    doc   = msg.get("document")
                    if photo or (doc and (doc.get("mime_type") or "").startswith("image/")):
                        file_id = photo[-1]["file_id"] if photo else doc["file_id"]
                        caption = msg.get("caption", "").strip() or "Опиши эту картинку."
                        image_bytes = self._download_file(file_id)
                        if image_bytes:
                            _log.info(f"← TG: photo ({len(image_bytes)} bytes), caption={caption!r}")
                            self.image_received.emit(caption, image_bytes)
                        continue

                    if not text:
                        continue

                    _log.info(f"← TG: {text[:80]!r}")
                    self.message_received.emit(text)
            except Exception as e:
                if self._running:
                    _log.error(f"Poll error: {e}")
                    self.msleep(3000)

    def _get_updates(self) -> list:
        try:
            resp = self._session.get(
                self._url("getUpdates"),
                params={"offset": self._offset, "timeout": 1, "limit": 10},
                timeout=4,
            )
            data = resp.json()
            return data.get("result", []) if data.get("ok") else []
        except Exception:
            return []

    def _download_file(self, file_id: str) -> bytes | None:
        try:
            resp = self._session.get(self._url("getFile"), params={"file_id": file_id}, timeout=10)
            file_path = resp.json()["result"]["file_path"]
            url = f"https://api.telegram.org/file/bot{self._token}/{file_path}"
            data = self._session.get(url, timeout=30)
            return data.content
        except Exception as e:
            _log.error(f"download_file error: {e}")
            return None

    def _ready(self) -> bool:
        return bool(self._token and self._chat_id)

    def _url(self, method: str) -> str:
        return _API.format(token=self._token, method=method)
