import data.keystore as keystore
import data.config as config
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QLineEdit, QPushButton, QFrame, QWidget, QComboBox, QCheckBox,
)

_KEY_FIELDS = [
    ("GROK_API_KEY",     "Grok API Key",        "Вставьте ключ xai-...",           True),
    ("TELEGRAM_TOKEN",   "Telegram Bot Token",   "Вставьте токен от @BotFather...", True),
    ("TELEGRAM_CHAT_ID", "Telegram Chat ID",     "Ваш числовой chat_id...",         False),
]

_BILLING_FIELDS = [
    ("MGMT_API_KEY", "Management Key", "Ключ billing-reader (xai-token-...)", True),
    ("TEAM_ID",      "Team ID",        "UUID из console.x.ai/team/.../settings", False),
]

_TTS_VOICES = [
    ("ara", "Ara — тёплый, дружелюбный (быстрее)"),
    ("eve", "Eve — энергичный, живой (медленнее)"),
    ("sal", "Sal — ровный, универсальный"),
    ("rex", "Rex — уверенный, чёткий"),
    ("leo", "Leo — авторитетный, сильный"),
]

# (model_id, label с ценами)
_GROK_MODELS = [
    ("grok-4.3",  "grok-4.3   — $1.25 / $2.50 за 1M"),
    ("grok-4.20", "grok-4.20  — $2.00 / $6.00 за 1M"),
    ("grok-4.1",  "grok-4.1   — $0.20 / $0.50 за 1M"),
]


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(480)
        self.setFixedHeight(360)
        self.setModal(True)
        self._key_fields: dict[str, QLineEdit] = {}
        self._billing_fields: dict[str, QLineEdit] = {}
        self._billing_interval_field: QLineEdit | None = None
        self._history_field: QLineEdit | None = None
        self._model_combo: QComboBox | None = None
        self._web_search_combo: QComboBox | None = None
        self._save_actions: list = []
        self._tab_btns: dict[str, QPushButton] = {}
        self._tab_order: list[str] = []
        self._stack = QStackedWidget()
        self._build_ui()

    # ── Сохранение ──────────────────────────────────────────────────────────

    def _on_save(self):
        for action in self._save_actions:
            try:
                action()
            except Exception:
                pass
        self.accept()

    # ── Скелет ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Заголовок
        title_bar = QWidget()
        title_bar.setObjectName("settings_title_bar")
        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(16, 12, 16, 12)
        lbl = QLabel("Настройки")
        lbl.setObjectName("settings_title")
        tl.addWidget(lbl)
        root.addWidget(title_bar)
        root.addWidget(_hline())

        # Вкладки
        tab_bar = QWidget()
        tab_bar.setObjectName("settings_tab_bar")
        self._tab_layout = QHBoxLayout(tab_bar)
        self._tab_layout.setContentsMargins(8, 4, 8, 4)
        self._tab_layout.setSpacing(4)
        self._tab_layout.addStretch()
        root.addWidget(tab_bar)
        root.addWidget(_hline())

        root.addWidget(self._stack, 1)
        root.addWidget(_hline())

        # Футер
        footer = QWidget()
        footer.setObjectName("settings_footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.setSpacing(8)
        billing_link = QLabel('<a href="https://console.x.ai" style="color:#cdd6f4;text-decoration:none;">console.x.ai</a>')
        billing_link.setObjectName("settings_link")
        billing_link.setOpenExternalLinks(True)
        billing_link.setToolTip("Открыть консоль x.ai — баланс, расходы, API-ключи")
        fl.addWidget(billing_link)
        fl.addStretch()
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedSize(90, 30)
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("settings_save_btn")
        save_btn.setFixedSize(100, 30)
        save_btn.clicked.connect(self._on_save)
        fl.addWidget(cancel_btn)
        fl.addWidget(save_btn)
        root.addWidget(footer)

        self._add_tab("keys",    "Ключи",   self._build_keys_tab)
        self._add_tab("model",   "Модель",  self._build_model_tab)
        self._add_tab("voice",   "Голос",   self._build_voice_tab)
        self._add_tab("billing", "Биллинг", self._build_billing_tab)
        self._switch_tab("keys")

    # ── Система вкладок ──────────────────────────────────────────────────────

    def _add_tab(self, key: str, label: str, builder):
        btn = QPushButton(label)
        btn.setObjectName("tab_btn")
        btn.setCheckable(True)
        btn.setFixedHeight(26)
        btn.clicked.connect(lambda _=False, k=key: self._switch_tab(k))
        self._tab_layout.insertWidget(self._tab_layout.count() - 1, btn)
        self._tab_btns[key] = btn
        self._stack.addWidget(builder())
        self._tab_order.append(key)

    def _switch_tab(self, key: str):
        self._stack.setCurrentIndex(self._tab_order.index(key))
        for k, btn in self._tab_btns.items():
            btn.setChecked(k == key)

    # ── Вспомогательные ─────────────────────────────────────────────────────

    def _body_widget(self) -> tuple[QWidget, QVBoxLayout]:
        body = QWidget()
        body.setObjectName("settings_body")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)
        return body, lay

    def _row(self, lay: QVBoxLayout, label: str, widget: QWidget):
        row = QHBoxLayout()
        row.setSpacing(12)
        lbl = QLabel(label)
        lbl.setObjectName("settings_row_label")
        lbl.setFixedWidth(170)
        row.addWidget(lbl)
        row.addWidget(widget, 1)
        lay.addLayout(row)

    # ── Вкладка Ключи ───────────────────────────────────────────────────────

    def _build_keys_tab(self) -> QWidget:
        body, lay = self._body_widget()
        for key, label, placeholder, secret in _KEY_FIELDS:
            field = QLineEdit(keystore.get(key))
            field.setPlaceholderText(placeholder)
            field.setFixedHeight(28)
            field.setObjectName("settings_field")
            if secret:
                field.setEchoMode(QLineEdit.EchoMode.Password)
            self._key_fields[key] = field
            self._row(lay, label, field)

        lay.addStretch()
        self._save_actions.append(
            lambda: keystore.save_all({k: f.text().strip() for k, f in self._key_fields.items()})
        )
        return body

    # ── Вкладка Модель ──────────────────────────────────────────────────────

    def _build_model_tab(self) -> QWidget:
        body, lay = self._body_widget()

        # Выбор модели
        self._model_combo = QComboBox()
        current_model = config.get("model") or "grok-4.3"
        for model_id, label in _GROK_MODELS:
            self._model_combo.addItem(label, model_id)
        for i, (model_id, _) in enumerate(_GROK_MODELS):
            if model_id == current_model:
                self._model_combo.setCurrentIndex(i)
                break
        self._model_combo.setFixedHeight(28)
        self._row(lay, "Модель", self._model_combo)

        # История
        self._history_field = QLineEdit(str(config.get("history_limit") or 100))
        self._history_field.setFixedHeight(28)
        self._history_field.setObjectName("settings_field")
        self._row(lay, "История (сообщений)", self._history_field)

        # Поиск в интернете
        self._web_search_combo = QComboBox()
        self._web_search_combo.addItems(["Включён", "Выключён"])
        self._web_search_combo.setCurrentIndex(0 if config.get("web_search") else 1)
        self._web_search_combo.setFixedHeight(28)
        self._row(lay, "Поиск в интернете", self._web_search_combo)

        # Дигесты (выжимки дней)
        self._digests_combo = QComboBox()
        _digest_options = [
            (0, "Выключены"),
            (1, "1 день"),
            (2, "2 дня"),
            (3, "3 дня"),
            (5, "5 дней"),
            (10, "10 дней"),
        ]
        current_count = config.get("digests_count") or 0
        for val, label in _digest_options:
            self._digests_combo.addItem(label, val)
        for i, (val, _) in enumerate(_digest_options):
            if val == current_count:
                self._digests_combo.setCurrentIndex(i)
                break
        self._digests_combo.setFixedHeight(28)
        self._digests_combo.setToolTip("Сколько дней-выжимок подгружать в контекст при каждом запросе")
        self._row(lay, "Дигесты (выжимки)", self._digests_combo)

        lay.addStretch()

        self._save_actions.append(self._save_model_tab)
        return body

    def _save_model_tab(self):
        if self._model_combo:
            config.set("model", self._model_combo.currentData())
        if self._history_field:
            try:
                config.set("history_limit", int(self._history_field.text().strip()))
            except ValueError:
                pass
        if self._web_search_combo:
            config.set("web_search", self._web_search_combo.currentIndex() == 0)
        if self._digests_combo:
            config.set("digests_count", self._digests_combo.currentData())

    # ── Вкладка Голос ───────────────────────────────────────────────────────

    def _build_voice_tab(self) -> QWidget:
        body, lay = self._body_widget()

        self._tts_combo = QComboBox()
        self._tts_combo.addItem("Выключен", "")
        for voice_id, label in _TTS_VOICES:
            self._tts_combo.addItem(label, voice_id)
        current_voice = config.get("tts_voice") if config.get("tts_enabled") else ""
        for i in range(self._tts_combo.count()):
            if self._tts_combo.itemData(i) == current_voice:
                self._tts_combo.setCurrentIndex(i)
                break
        self._tts_combo.setFixedHeight(28)
        self._row(lay, "Голос озвучки", self._tts_combo)

        # Микрофон (Vosk)
        self._mic_check = QCheckBox()
        self._mic_check.setChecked(bool(config.get("mic_enabled")))
        self._mic_check.setToolTip(
            "При первом включении скачается модель Vosk (~45MB).\n"
            "Модель загружается в память при каждом старте приложения."
        )
        self._row(lay, "Микрофон (Vosk STT)", self._mic_check)

        hint = QLabel("При первом включении скачается модель ~45MB.\nЗагружается в фоне при старте.")
        hint.setObjectName("settings_row_label")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        lay.addStretch()
        self._save_actions.append(self._save_voice_tab)
        return body

    def _save_voice_tab(self):
        voice_id = self._tts_combo.currentData()
        config.set("tts_enabled", bool(voice_id))
        if voice_id:
            config.set("tts_voice", voice_id)
        config.set("mic_enabled", self._mic_check.isChecked())

    # ── Вкладка Биллинг ─────────────────────────────────────────────────────

    def _build_billing_tab(self) -> QWidget:
        body, lay = self._body_widget()

        hint = QLabel("Ключи для мониторинга баланса xAI.\n"
                      "Создай Management Key в console.x.ai > Settings.")
        hint.setObjectName("settings_row_label")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        for key, label, placeholder, secret in _BILLING_FIELDS:
            field = QLineEdit(keystore.get(key))
            field.setPlaceholderText(placeholder)
            field.setFixedHeight(28)
            field.setObjectName("settings_field")
            if secret:
                field.setEchoMode(QLineEdit.EchoMode.Password)
            self._billing_fields[key] = field
            self._row(lay, label, field)

        self._billing_interval_field = QLineEdit(str(config.get("billing_interval") or 60))
        self._billing_interval_field.setFixedHeight(28)
        self._billing_interval_field.setObjectName("settings_field")
        self._billing_interval_field.setPlaceholderText("60")
        self._row(lay, "Интервал (сек)", self._billing_interval_field)

        lay.addStretch()
        self._save_actions.append(self._save_billing_tab)
        return body

    def _save_billing_tab(self):
        data = {k: keystore.get(k) for k in [f[0] for f in _KEY_FIELDS]}
        data.update({k: f.text().strip() for k, f in self._billing_fields.items()})
        keystore.save_all(data)
        if self._billing_interval_field:
            try:
                val = max(10, int(self._billing_interval_field.text().strip()))
                config.set("billing_interval", val)
            except ValueError:
                pass
