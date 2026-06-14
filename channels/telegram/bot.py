import threading
import requests as _req
from PySide6.QtCore import QThread, Signal
import data.logger as logger
import data.keystore as keystore

_log = logger.get_logger("telegram")
_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramBot(QThread):
    message_received = Signal(str)   # входящий текст от пользователя

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token    = keystore.get("TELEGRAM_TOKEN") or ""
        self._chat_id  = str(keystore.get("TELEGRAM_CHAT_ID") or "")
        self._offset   = 0
        self._running  = False
        self._session  = _req.Session()
        self._stop_typing = threading.Event()

    # ── отправка ─────────────────────────────────────────────────────────────

    def send(self, text: str):
        if not self._ready():
            return
        try:
            self._session.post(
                self._url("sendMessage"),
                json={"chat_id": self._chat_id, "text": text},
                timeout=10,
            )
        except Exception as e:
            _log.error(f"send error: {e}")

    def send_tool(self, label: str):
        """Отправить курсивный индикатор вызова инструмента."""
        if not self._ready():
            return
        try:
            self._session.post(
                self._url("sendMessage"),
                json={
                    "chat_id": self._chat_id,
                    "text": f"<i>↗ {label}...</i>",
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

    def run(self):
        if not self._token:
            _log.warning("No Telegram token configured, bot disabled")
            return
        _log.info(f"Polling started, chat_id={self._chat_id}")
        self._running = True
        while self._running:
            try:
                updates = self._get_updates()
                for upd in updates:
                    self._offset = upd["update_id"] + 1
                    msg = upd.get("message") or upd.get("edited_message")
                    if not msg:
                        continue
                    cid = str(msg["chat"]["id"])
                    text = msg.get("text", "").strip()
                    if not text:
                        continue

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

    def _ready(self) -> bool:
        return bool(self._token and self._chat_id)

    def _url(self, method: str) -> str:
        return _API.format(token=self._token, method=method)
