import sys
import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QScrollArea, QLabel, QFrame,
    QSizePolicy, QMenu, QApplication, QFileDialog
)
from PySide6.QtGui import QPixmap
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QProcess, QTimer, QThread
from PySide6.QtGui import QFont
import data.config as config
import data.token_log as token_log
from data.billing import fetch_balance

from ui.theme import (
    ICONS, MID_BUTTONS, ICON_FONT, COLORS,
    INPUT_H, BTN_SIZE, MID_SIZE,
    list_themes, get_active_path, set_active_theme,
)
import data.chat_history as chat_history
from core.message_worker import MessageWorker
import tools.tts as tts
from core.daily_log import append_message as log_message
from channels.telegram.bot import TelegramBot


def _h_line():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


class _InnerEdit(QTextEdit):
    send_requested = Signal()

    def keyPressEvent(self, event):
        if (event.key() == Qt.Key.Key_Return
                and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            self.send_requested.emit()
        else:
            super().keyPressEvent(event)


class InputBubble(QFrame):
    send_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("input_bubble")
        self.setFixedHeight(INPUT_H)

        self.editor = _InnerEdit()
        self.editor.setObjectName("inner_input")
        self.editor.setPlaceholderText(
            "Напишите сообщение...   (Enter — отправить, Shift+Enter — новая строка)"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)

        self.send_btn = QPushButton(ICONS["send"], self)
        self.send_btn.setObjectName("icon_btn")
        self.send_btn.setFixedSize(34, 34)
        self.send_btn.setFont(QFont(ICON_FONT, 15))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_send)
        self.editor.send_requested.connect(self._on_send)
        self._place_btn()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_btn()

    def _place_btn(self):
        self.send_btn.move(
            self.width() - self.send_btn.width() - 7,
            (self.height() - self.send_btn.height()) // 2,
        )

    def _on_send(self):
        text = self.editor.toPlainText().strip()
        self.send_requested.emit(text)
        if text:
            self.editor.clear()


class _ImageWidget(QFrame):
    """Картинка с рамкой и открытием по клику."""
    def __init__(self, px: QPixmap, path: str = "", parent=None):
        super().__init__(parent)
        self._path = path
        self.setObjectName("image_frame")
        self.setStyleSheet(
            "QFrame#image_frame {"
            "  border: 2px solid rgba(210, 210, 210, 0.5);"
            "  border-radius: 8px;"
            "  background: rgba(255, 255, 255, 0.04);"
            "}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if path:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl = QLabel()
        lbl.setPixmap(px)
        lbl.setContentsMargins(0, 0, 0, 0)
        lbl.setStyleSheet("border: none; background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)  # 8px поле по периметру
        layout.setSpacing(0)
        layout.addWidget(lbl)

    def mousePressEvent(self, event):
        if self._path:
            import os
            try:
                os.startfile(self._path)
            except Exception:
                pass
        super().mousePressEvent(event)


class _BillingWorker(QThread):
    result = Signal(object)

    def run(self):
        self.result.emit(fetch_balance())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grok Agent")
        self.resize(920, 720)
        self.setMinimumSize(640, 480)
        self._worker: MessageWorker | None = None
        self._tg: TelegramBot | None = None
        self._billing_worker: _BillingWorker | None = None
        self._speak_buttons: list = []
        self._tts_workers: list = []
        self._pending: dict | None = None   # {"type": "image"|"file", "bytes"|"content": ..., "name": str}
        self._attach_btn = None             # ссылка на кнопку в mid_buttons
        self._request_start = 0.0
        self._active_tool = ""

        self._think_timer = QTimer(self)
        self._think_timer.setInterval(100)
        self._think_timer.timeout.connect(self._update_thinking)

        self._sysinfo_timer = QTimer(self)
        self._sysinfo_timer.setInterval(2000)
        self._sysinfo_timer.timeout.connect(self._update_sysinfo)
        self._sysinfo_timer.start()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_toolbar())
        root.addWidget(_h_line())
        root.addWidget(self._build_content(), stretch=1)
        root.addWidget(_h_line())
        root.addWidget(self._build_status())

        self._load_history()
        self._start_tg()
        self._start_billing_timer()

    # ── Тулбар ──────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(48)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 0, 12, 0)
        tb.setSpacing(6)

        self._header_icon = QLabel(ICONS["header"])
        self._header_icon.setObjectName("header_icon")
        self._update_antenna()

        title = QLabel("Grok Agent")
        title.setObjectName("title_label")
        self._model_label = QLabel(config.get("model") or "grok-4.3")
        self._model_label.setObjectName("model_label")
        self._msg_counter = QLabel("0/100")
        self._msg_counter.setObjectName("model_label")

        icon_font = QFont(ICON_FONT, 17)

        self._btn_theme = QPushButton(ICONS["theme"])
        self._btn_theme.setObjectName("icon_btn")
        self._btn_theme.setFont(icon_font)
        self._btn_theme.setFixedSize(BTN_SIZE, BTN_SIZE)
        self._btn_theme.setToolTip("Выбрать тему")
        self._btn_theme.clicked.connect(self._show_theme_menu)

        btn_settings = QPushButton(ICONS["settings"])
        btn_settings.setObjectName("icon_btn")
        btn_settings.setFont(icon_font)
        btn_settings.setFixedSize(BTN_SIZE, BTN_SIZE)
        btn_settings.setToolTip("Настройки")
        btn_settings.clicked.connect(self._show_settings)

        self._balance_label = QLabel("")
        self._balance_label.setObjectName("model_label")
        self._balance_label.setToolTip("billing")
        self._balance_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._balance_label.mousePressEvent = lambda _: __import__("webbrowser").open("https://console.x.ai/team/default/billing")

        tb.addWidget(self._header_icon)
        tb.addWidget(title)
        tb.addWidget(self._model_label)
        tb.addWidget(self._msg_counter)
        tb.addStretch()
        tb.addWidget(self._balance_label)
        tb.addWidget(self._btn_theme)
        tb.addWidget(btn_settings)
        return toolbar

    def _show_theme_menu(self):
        menu = QMenu(self)
        active = get_active_path().name
        for name in list_themes():
            label = name.replace("theme_", "").replace(".json", "").capitalize()
            action = menu.addAction(label)
            action.setData(name)
            if name == active:
                action.setEnabled(False)
        chosen = menu.exec(self._btn_theme.mapToGlobal(
            self._btn_theme.rect().bottomLeft()
        ))
        if chosen and chosen.data():
            set_active_theme(chosen.data())
            QProcess.startDetached(sys.executable, sys.argv)
            QApplication.instance().quit()

    # ── Контент ─────────────────────────────────────────────────────────────

    def _build_content(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(self._build_chat(), stretch=1)
        layout.addLayout(self._build_input_row())
        layout.addLayout(self._build_mid_buttons())
        return widget

    # ── Чат ─────────────────────────────────────────────────────────────────

    def _build_chat(self):
        frame = QFrame()
        frame.setObjectName("chat_frame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("chat_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._chat_content = QWidget()
        self._chat_content.setObjectName("chat_content")
        self._chat_layout = QVBoxLayout(self._chat_content)
        self._chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._chat_layout.setSpacing(8)
        self._chat_layout.setContentsMargins(12, 12, 12, 12)

        scroll.setWidget(self._chat_content)
        fl.addWidget(scroll)

        self._scroll = scroll
        self._last_bubble = None
        return frame

    def _load_history(self):
        messages = chat_history.load()
        for m in messages:
            img_bytes = None
            img_path = m.get("image_path", "")
            if img_path:
                import pathlib as _pl
                p = _pl.Path(img_path)
                if p.exists():
                    img_bytes = p.read_bytes()
            self.add_bubble(m["text"], is_user=(m["role"] == "user"), ts=m.get("ts", ""), image=img_bytes, image_path=img_path)
        self._update_counter()
        # Один скролл в конце — после того как все пузыри добавлены
        from PySide6.QtCore import QTimer
        QTimer.singleShot(200, self._scroll_to_bottom)

    def _update_counter(self):
        count = len(chat_history.load())
        limit = config.get("history_limit") or 100
        self._msg_counter.setText(f"{count}/{limit}")

    def add_bubble(self, text: str, is_user: bool, ts: str = "", image: bytes | None = None, image_path: str = ""):
        if not ts:
            ts = datetime.now().strftime("%H:%M")
        name = "Вы" if is_user else "Грок"

        bubble = QFrame()
        bubble.setObjectName("bubble_user" if is_user else "bubble_agent")
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        # Заголовок: [время] Имя   🔊 (только для агента)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        prefix = QLabel(f"[{ts}] {name}")
        prefix.setObjectName("bubble_prefix")
        header_row.addWidget(prefix)
        header_row.addStretch()

        if not is_user:
            from ui.theme import ICON_FONT
            speak_btn = QPushButton(chr(0xE995))  # Volume icon
            speak_btn.setObjectName("bubble_speak_btn")
            speak_btn.setFixedSize(22, 22)
            speak_btn.setFont(QFont(ICON_FONT, 11))
            speak_btn.setToolTip("Озвучить")
            speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            speak_btn.clicked.connect(lambda _=False, t=text: self._speak(t))
            header_row.addWidget(speak_btn)
            self._speak_buttons.append(speak_btn)

        bl.addLayout(header_row)

        lbl = QLabel(tts.shorten_urls(text) if not is_user else text)
        lbl.setObjectName("bubble_text")
        lbl.setWordWrap(True)
        bl.addWidget(lbl)

        if image:
            px = QPixmap()
            px.loadFromData(image)
            if not px.isNull():
                scaled = px.scaledToWidth(480, Qt.TransformationMode.SmoothTransformation)
                img_widget = _ImageWidget(scaled, path=image_path)
                from PySide6.QtWidgets import QHBoxLayout as _QHBox
                img_row = _QHBox()
                img_row.setContentsMargins(12, 4, 12, 8)
                img_row.addWidget(img_widget)
                img_row.addStretch()
                bl.addLayout(img_row)

        self._last_bubble = bubble
        self._chat_layout.addWidget(bubble)

    def _scroll_to_bottom(self):
        if self._last_bubble:
            self._scroll.ensureWidgetVisible(self._last_bubble)

    # ── Ввод ────────────────────────────────────────────────────────────────

    def _build_input_row(self):
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.input_bubble = InputBubble()
        self.input_bubble.send_requested.connect(self._on_send)

        mic_btn = QPushButton(ICONS["mic"])
        mic_btn.setObjectName("mic_btn")
        mic_btn.setFont(QFont(ICON_FONT, 17))
        mic_btn.setFixedSize(MID_SIZE, MID_SIZE)
        mic_btn.setToolTip("Нажмите и держите для записи")

        row.addWidget(self.input_bubble)
        row.addWidget(mic_btn)
        return row

    # ── Нижние кнопки ───────────────────────────────────────────────────────

    def _build_mid_buttons(self):
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        font = QFont(ICON_FONT, 16)
        for key, tip in MID_BUTTONS:
            btn = QPushButton(ICONS[key])
            btn.setObjectName("mid_btn")
            btn.setFont(font)
            btn.setFixedSize(MID_SIZE, MID_SIZE)
            btn.setToolTip(tip)
            if key == "attach":
                self._attach_btn = btn
                btn.clicked.connect(self._on_attach)
            elif key == "clear_chat":
                btn.clicked.connect(self._on_clear_chat)
            row.addWidget(btn)
        return row

    # ── Статус ──────────────────────────────────────────────────────────────

    def _build_status(self):
        bar = QWidget()
        bar.setObjectName("status_bar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)

        self.status_left = QLabel("Готов.")
        self.status_left.setObjectName("status_left")
        self.status_right = QLabel("CPU: — | RAM: — | C: —")
        self.status_right.setObjectName("status_right")

        layout.addWidget(self.status_left)
        layout.addStretch()
        layout.addWidget(self.status_right)
        return bar

    # ── Telegram ────────────────────────────────────────────────────────────

    def _start_tg(self):
        self._tg = TelegramBot(parent=self)
        self._tg.message_received.connect(self._on_tg_message)
        self._tg.image_received.connect(self._on_tg_image)
        self._tg.clear_requested.connect(self._do_clear)
        self._tg.start()

    def _on_tg_message(self, text: str):
        if self._worker and self._worker.isRunning():
            return
        ts = datetime.now().strftime("%H:%M")
        self.add_bubble(text, is_user=True, ts=ts)
        chat_history.append("user", text)
        log_message("user", text)
        self._update_counter()
        self.input_bubble.setEnabled(False)
        self._start_worker()

    def _on_tg_image(self, caption: str, image_bytes: bytes):
        if self._worker and self._worker.isRunning():
            return
        ts = datetime.now().strftime("%H:%M")
        img_path = chat_history.save_image(image_bytes)
        self.add_bubble(caption, is_user=True, ts=ts, image=image_bytes, image_path=img_path)
        self._scroll_to_bottom()
        chat_history.append("user", caption, image_path=img_path)
        log_message("user", caption)
        self._update_counter()
        self.input_bubble.setEnabled(False)
        self._start_worker(images=[image_bytes])

    # ── Логика ──────────────────────────────────────────────────────────────

    def _update_antenna(self):
        on = config.get("web_search")
        color = COLORS["text"] if on else "#FF5252"
        self._header_icon.setStyleSheet(f"color: {color};")

    def _show_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._update_antenna()
            self._restart_billing_timer()
            self._model_label.setText(config.get("model") or "grok-4.3")

    # ── Биллинг ─────────────────────────────────────────────────────────────

    def _start_billing_timer(self):
        self._refresh_billing()
        interval = (config.get("billing_interval") or 60) * 1000
        self._billing_timer = QTimer(self)
        self._billing_timer.timeout.connect(self._refresh_billing)
        self._billing_timer.start(interval)

    def _restart_billing_timer(self):
        interval = (config.get("billing_interval") or 60) * 1000
        self._billing_timer.setInterval(interval)
        self._refresh_billing()

    def _refresh_billing(self):
        if self._billing_worker and self._billing_worker.isRunning():
            return
        self._billing_worker = _BillingWorker()
        self._billing_worker.result.connect(self._on_billing_result)
        self._billing_worker.start()

    def _on_billing_result(self, data):
        if data is None:
            self._balance_label.setText("")
            self._balance_label.setStyleSheet("")
            return
        usd = data["remaining"]
        if usd < 1:
            self._balance_label.setStyleSheet("color: #f38ba8; padding-left: 6px; padding-right: 24px;")
        else:
            self._balance_label.setStyleSheet("padding-left: 6px; padding-right: 24px;")
        self._balance_label.setText(f"billing ${usd:.2f}")

    # ── Статус ──────────────────────────────────────────────────────────────

    def _set_status(self, text: str, error: bool = False):
        short = text if len(text) <= 80 else text[:77] + "..."
        self.status_left.setText(short)
        if error:
            self.status_left.setStyleSheet("color: #f38ba8;")
            QTimer.singleShot(6000, lambda: self.status_left.setStyleSheet(""))
        else:
            self.status_left.setStyleSheet("")

    def _update_thinking(self):
        elapsed = time.monotonic() - self._request_start
        if self._active_tool:
            label = self._active_tool[:50]
            self.status_left.setText(f"{label}  {elapsed:.1f}с")
        else:
            self.status_left.setText(f"Думаю...  {elapsed:.1f}с")

    def _update_sysinfo(self):
        try:
            import psutil
            cpu  = psutil.cpu_percent()
            ram  = psutil.virtual_memory().percent
            disk = psutil.disk_usage("C:/").free / (1024 ** 3)
            self.status_right.setText(f"CPU: {cpu:.0f}% | RAM: {ram:.0f}% | C: {disk:.1f}GB")
        except Exception:
            pass

    _IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".ico"}

    def _on_attach(self):
        # Если уже что-то прикреплено — снимаем
        if self._pending:
            self._pending = None
            if self._attach_btn:
                self._attach_btn.setToolTip("Прикрепить файл или картинку")
                self._attach_btn.setStyleSheet("")
            return

        path, _ = QFileDialog.getOpenFileName(self, "Прикрепить файл", "", "Все файлы (*.*)")
        if not path:
            return

        import pathlib
        p = pathlib.Path(path)
        name = p.name
        ext = p.suffix.lower()

        if ext in self._IMG_EXTS:
            self._pending = {"type": "image", "bytes": p.read_bytes(), "name": name}
        else:
            raw = p.read_bytes()
            # Режем на 100 KB чтобы не забить контекст
            try:
                content = raw[:100_000].decode("utf-8", errors="replace")
                if len(raw) > 100_000:
                    content += f"\n\n... [обрезано, показано 100KB из {len(raw)//1024}KB]"
            except Exception:
                content = f"[Не удалось прочитать файл как текст: {name}]"
            self._pending = {"type": "file", "content": content, "name": name}

        if self._attach_btn:
            self._attach_btn.setToolTip(f"📎 {name}  (нажми снова — снять)")
            self._attach_btn.setStyleSheet("color: #a6e3a1;")
        kind = "картинка" if self._pending["type"] == "image" else "файл"
        self._set_status(f"📎 Прикреплён {kind}: {name}")

    def _on_send(self, text: str):
        if self._worker and self._worker.isRunning():
            return
        if not text and not self._pending:
            return
        ts = datetime.now().strftime("%H:%M")
        pending = self._pending
        images = []
        img_bytes_for_bubble = None
        img_path = ""
        full_text = text

        if pending:
            if pending["type"] == "image":
                img_bytes = pending["bytes"]
                images = [img_bytes]
                img_bytes_for_bubble = img_bytes
                img_path = chat_history.save_image(img_bytes)
            elif pending["type"] == "file":
                name = pending["name"]
                content = pending["content"]
                full_text = f"{text}\n\n📎 {name}:\n```\n{content}\n```" if text else f"📎 {name}:\n```\n{content}\n```"

        self.add_bubble(full_text, is_user=True, ts=ts, image=img_bytes_for_bubble, image_path=img_path)
        self._scroll_to_bottom()
        chat_history.append("user", full_text, image_path=img_path)
        log_message("user", full_text)
        self._update_counter()
        self.input_bubble.setEnabled(False)
        self._pending = None
        if self._attach_btn:
            self._attach_btn.setToolTip("Прикрепить файл или картинку")
            self._attach_btn.setStyleSheet("")
        self._start_worker(images=images)

    def _start_worker(self, images: list | None = None):
        self._request_start = time.monotonic()
        self._active_tool = ""
        self._think_timer.start()
        self._worker = MessageWorker(chat_history.load(), images=images)
        self._worker.finished.connect(self._on_reply)
        self._worker.error.connect(self._on_error)
        self._worker.tool_used.connect(self._on_tool_used)
        self._worker.image_ready.connect(self._on_image_ready)
        self._worker.start()
        if self._tg:
            self._tg.start_typing()

    def _on_reply(self, text: str, elapsed: float):
        self._think_timer.stop()
        self._active_tool = ""
        if self._tg:
            self._tg.stop_typing()
        ts = datetime.now().strftime("%H:%M")
        chat_history.append("agent", text, elapsed)
        log_message("agent", text)
        self.add_bubble(text, is_user=False, ts=ts)
        self._scroll_to_bottom()
        self._update_counter()
        self._set_status(f"Готов.  ответ за {elapsed:.1f}с")
        self.input_bubble.setEnabled(True)
        if self._tg:
            in_t, out_t = token_log.get()
            footer = f"\n\n({elapsed:.1f}с · {in_t + out_t:,} ток.)" if (in_t + out_t) else f"\n\n({elapsed:.1f}с)"
            self._tg.send(text + footer)

    def _on_image_ready(self, path: str):
        """Картинка сгенерирована/скриншот готов — показать в чате и отправить в Telegram."""
        import pathlib
        try:
            img_bytes = pathlib.Path(path).read_bytes()
        except Exception:
            return
        chat_history.append("agent", "", image_path=path)
        self.add_bubble("", is_user=False, image=img_bytes, image_path=path)
        self._scroll_to_bottom()
        if self._tg:
            self._tg.send_image(img_bytes)

    def _on_tool_used(self, name: str, label: str):
        self._active_tool = label
        from ui.theme import TOOL_ICONS, TOOL_ICON_DEFAULT, ICON_FONT
        if self._tg:
            self._tg.send_tool(name, label)
        bubble = QFrame()
        bubble.setObjectName("bubble_tool")
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        from PySide6.QtWidgets import QHBoxLayout
        icon_char = TOOL_ICONS.get(name, TOOL_ICON_DEFAULT)
        row = QHBoxLayout()
        row.setContentsMargins(12, 4, 12, 4)
        row.setSpacing(6)
        icon_lbl = QLabel(icon_char)
        icon_lbl.setObjectName("bubble_tool_icon")
        icon_lbl.setFixedWidth(18)
        text_lbl = QLabel(f"{label}...")
        text_lbl.setObjectName("bubble_tool_text")
        row.addWidget(icon_lbl)
        row.addWidget(text_lbl)
        row.addStretch()
        bl.addLayout(row)
        self._last_bubble = bubble
        self._chat_layout.addWidget(bubble)
        self._scroll_to_bottom()

    def _on_clear_chat(self):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Очистить чат",
            "Удалить всю историю чата?\nОтменить нельзя.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._do_clear()

    def _do_clear(self):
        chat_history.clear()
        while self._chat_layout.count():
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._last_bubble = None
        self._update_counter()
        self._set_status("История очищена.")

    def _set_speak_enabled(self, enabled: bool):
        for btn in self._speak_buttons:
            btn.setEnabled(enabled)

    def _speak(self, text: str):
        if not tts.is_enabled():
            return
        self._set_speak_enabled(False)
        self._set_status("Озвучиваю...")

        def _on_done(audio: bytes):
            tts.play(audio, on_finished=lambda: (
                self._set_speak_enabled(True),
                self._set_status("Готов."),
            ))

        def _on_error(e: str):
            self._set_speak_enabled(True)
            self._set_status(f"TTS ошибка: {e}", error=True)

        worker = tts.TTSWorker(text)
        worker.done.connect(_on_done)
        worker.error.connect(_on_error)
        worker.start()
        self._tts_workers.append(worker)

    def _on_error(self, msg: str):
        self._think_timer.stop()
        self._active_tool = ""
        if self._tg:
            self._tg.stop_typing()
        self.input_bubble.setEnabled(True)
        self._set_status(f"Ошибка: {msg}", error=True)
        self.input_bubble.setEnabled(True)
