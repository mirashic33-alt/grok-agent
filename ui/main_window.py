import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QScrollArea, QLabel, QFrame,
    QSizePolicy, QMenu, QApplication
)
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QProcess, QTimer
from PySide6.QtGui import QFont
import data.config as config
import data.token_log as token_log

from ui.theme import (
    ICONS, MID_ICONS, MID_TIPS, ICON_FONT, COLORS,
    INPUT_H, BTN_SIZE, MID_SIZE,
    list_themes, get_active_path, set_active_theme,
)
import data.chat_history as chat_history
from core.message_worker import MessageWorker
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
        if text:
            self.send_requested.emit(text)
            self.editor.clear()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grok Agent")
        self.resize(920, 720)
        self.setMinimumSize(640, 480)
        self._worker: MessageWorker | None = None
        self._tg: TelegramBot | None = None

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
        model = QLabel("grok-4.3")
        model.setObjectName("model_label")
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

        tb.addWidget(self._header_icon)
        tb.addWidget(title)
        tb.addWidget(model)
        tb.addWidget(self._msg_counter)
        tb.addStretch()
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
        return frame

    def _load_history(self):
        messages = chat_history.load()
        for m in messages:
            self.add_bubble(m["text"], is_user=(m["role"] == "user"), ts=m.get("ts", ""))
        self._update_counter()
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _update_counter(self):
        count = len(chat_history.load())
        limit = config.get("history_limit") or 100
        self._msg_counter.setText(f"{count}/{limit}")

    def add_bubble(self, text: str, is_user: bool, ts: str = ""):
        if not ts:
            ts = datetime.now().strftime("%H:%M")
        name = "Вы" if is_user else "Грок"

        bubble = QFrame()
        bubble.setObjectName("bubble_user" if is_user else "bubble_agent")
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        prefix = QLabel(f"[{ts}] {name}")
        prefix.setObjectName("bubble_prefix")

        lbl = QLabel(text)
        lbl.setObjectName("bubble_text")
        lbl.setWordWrap(True)

        bl.addWidget(prefix)
        bl.addWidget(lbl)

        self._chat_layout.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

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
        for icon, tip in zip(MID_ICONS, MID_TIPS):
            btn = QPushButton(icon)
            btn.setObjectName("mid_btn")
            btn.setFont(font)
            btn.setFixedSize(MID_SIZE, MID_SIZE)
            btn.setToolTip(tip)
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
        self._tg.start()

    def _on_tg_message(self, text: str):
        if self._worker and self._worker.isRunning():
            return
        ts = datetime.now().strftime("%H:%M")
        self.add_bubble(text, is_user=True, ts=ts)
        chat_history.append("user", text)
        log_message("user", text)
        self._update_counter()
        self.status_left.setText("Думаю...")
        self.input_bubble.setEnabled(False)
        self._start_worker()

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

    def _on_send(self, text: str):
        if self._worker and self._worker.isRunning():
            return
        ts = datetime.now().strftime("%H:%M")
        self.add_bubble(text, is_user=True, ts=ts)
        chat_history.append("user", text)
        log_message("user", text)
        self._update_counter()
        self.status_left.setText("Думаю...")
        self.input_bubble.setEnabled(False)
        self._start_worker()

    def _start_worker(self):
        self._worker = MessageWorker(chat_history.load())
        self._worker.finished.connect(self._on_reply)
        self._worker.error.connect(self._on_error)
        self._worker.tool_used.connect(self._on_tool_used)
        self._worker.start()
        if self._tg:
            self._tg.start_typing()

    def _on_reply(self, text: str, elapsed: float):
        if self._tg:
            self._tg.stop_typing()
        ts = datetime.now().strftime("%H:%M")
        chat_history.append("agent", text, elapsed)
        log_message("agent", text)
        self.add_bubble(text, is_user=False, ts=ts)
        self._update_counter()
        self.status_left.setText(f"Готов.  ({elapsed:.1f} сек)")
        self.input_bubble.setEnabled(True)
        if self._tg:
            in_t, out_t = token_log.get()
            footer = f"\n\n({elapsed:.1f}с · {in_t + out_t:,} ток.)" if (in_t + out_t) else f"\n\n({elapsed:.1f}с)"
            self._tg.send(text + footer)

    def _on_tool_used(self, label: str):
        if self._tg:
            self._tg.send_tool(label)
        bubble = QFrame()
        bubble.setObjectName("bubble_tool")
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(f"↗ {label}...")
        lbl.setObjectName("bubble_tool_text")
        bl.addWidget(lbl)
        self._chat_layout.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _on_error(self, msg: str):
        if self._tg:
            self._tg.stop_typing()
        self.status_left.setText(f"Ошибка: {msg}")
        self.input_bubble.setEnabled(True)
