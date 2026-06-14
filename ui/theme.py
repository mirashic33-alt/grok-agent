import json, pathlib, sys

ROOT       = pathlib.Path(__file__).parent.parent
THEMES_DIR = ROOT / "themes"
_DEFAULT   = "dark.json"

sys.path.insert(0, str(ROOT))
from data import config as _cfg


def get_active_path() -> pathlib.Path:
    name = _cfg.get("theme") or _DEFAULT
    p = THEMES_DIR / name
    return p if p.exists() else THEMES_DIR / _DEFAULT


def set_active_theme(name: str):
    _cfg.set("theme", name)


def list_themes() -> list[str]:
    return sorted(p.name for p in THEMES_DIR.glob("*.json"))


def _load() -> dict:
    return json.loads(get_active_path().read_text(encoding="utf-8"))


_j = _load()

COLORS = {
    "bg":           _j["bg_color"],
    "toolbar_bg":   _j["bg_color"],
    "chat_bg":      _j["chat_bg"],
    "input_bg":     _j["input_bg"],
    "text":         _j["text_color"],
    "border":       _j["border_color"],
    "btn_bg":       _j["button_bg"],
    "btn_hover":    _j["button_hover_bg"],
    "btn_pressed":  _j["button_pressed_bg"],
    "bubble_user":  _j["user_bubble_bg"],
    "bubble_ubrd":  _j["user_bubble_border"],
    "bubble_agent": _j["agent_bubble_bg"],
    "bubble_abrd":  _j["agent_bubble_border"],
    "bubble_text":  _j["bubble_text_color"],
    "dim_text":     _j["bubble_prefix_color"],
    "status_text":  _j["bubble_prefix_color"],
}

ICON_FONT = "Segoe MDL2 Assets"
RADIUS    = _j["border_radius"]
INPUT_H   = _j["input_height"]
BTN_SIZE  = 32    # квадратные кнопки тулбара и mic
MID_SIZE  = 36    # нижние кнопки

ICONS = {
    "send":     chr(0xE724),
    "mic":      chr(0xE720),
    "settings": chr(0xE713),
    "theme":    chr(0xE771),
    "header":   chr(0xEC44),   # менять здесь если нужна другая иконка
    "antenna":  chr(0xECA5),   # NetworkTower — иконка интернета
}

ANTENNA_ON_COLOR  = "#4FC3F7"   # голубой — интернет включён

MID_ICONS = [chr(0xE8A7), chr(0xE8B7), chr(0xE74D), chr(0xE916), chr(0xE712)]
MID_TIPS  = ["Открыть файл", "Открыть папку", "Очистить чат", "Таймер", "Ещё"]


def build_qss():
    c = COLORS
    r = RADIUS
    f = ICON_FONT
    return f"""
QWidget, QDialog {{
    background-color: {c['bg']};
    color: {c['text']};
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
}}
QLabel {{
    background-color: transparent;
    color: {c['text']};
}}
QComboBox {{
    background-color: {c['btn_bg']};
    color: {c['text']};
    border: 1px solid {c['bubble_ubrd']};
    border-radius: {r}px;
    padding: 3px 8px;
    font-size: 12px;
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {c['input_bg']};
    color: {c['text']};
    border: 1px solid {c['bubble_ubrd']};
    selection-background-color: {c['btn_hover']};
    outline: none;
}}

/* Тулбар */
QWidget#toolbar {{
    background-color: {c['toolbar_bg']};
}}
QLabel#title_label {{
    font-size: 24px;
    color: {c['text']};
}}
QLabel#header_icon {{
    font-family: '{f}';
    font-size: 28px;
    color: {c['text']};
    background-color: transparent;
    padding-right: 4px;
}}
QLabel#antenna_icon {{
    font-family: '{f}';
    font-size: 17px;
    background-color: transparent;
    padding: 0px 2px;
}}
QLabel#model_label {{
    font-size: 13px;
    color: {c['dim_text']};
    padding-left: 6px;
}}

/* Разделители */
QFrame[frameShape="4"] {{
    border: none;
    background-color: {c['border']};
    max-height: 1px;
}}

/* Чат */
QScrollArea#chat_scroll,
QScrollArea#chat_scroll > QWidget,
QWidget#chat_content {{
    background-color: transparent;
    border: none;
}}
QFrame#chat_frame {{
    background-color: {c['chat_bg']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
}}

/* Пузыри */
QFrame#bubble_user {{
    background-color: {c['bubble_user']};
    border: 1px solid {c['bubble_ubrd']};
    border-radius: {r}px;
}}
QFrame#bubble_agent {{
    background-color: {c['bubble_agent']};
    border: 1px solid {c['bubble_abrd']};
    border-radius: {r}px;
}}
QLabel#bubble_prefix {{
    font-size: 11px;
    color: {c['dim_text']};
    background-color: transparent;
    padding: 6px 12px 0px 12px;
}}
QLabel#bubble_text {{
    font-size: 13px;
    color: {c['bubble_text']};
    background-color: transparent;
    padding: 4px 12px 8px 12px;
}}
QFrame#bubble_tool {{
    background-color: transparent;
    border: 1px solid {c['border']};
    border-radius: {r}px;
}}
QLabel#bubble_tool_text {{
    font-size: 11px;
    color: {c['dim_text']};
    background-color: transparent;
    padding: 4px 12px;
    font-style: italic;
}}

/* Поле ввода */
QFrame#input_bubble {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
}}
QTextEdit#inner_input {{
    background-color: transparent;
    color: {c['text']};
    border: none;
    padding: 8px 40px 8px 10px;
    font-size: 13px;
}}

/* Кнопки */
QPushButton {{
    background-color: {c['btn_bg']};
    color: {c['text']};
    border: 1px solid {c['bubble_ubrd']};
    border-radius: {r}px;
    padding: 5px 10px;
}}
QPushButton:hover {{
    background-color: {c['btn_hover']};
}}
QPushButton:pressed {{
    background-color: {c['btn_pressed']};
}}

/* Иконочные кнопки (тулбар + mic) */
QPushButton#icon_btn {{
    font-family: '{f}';
    font-size: 17px;
    padding: 0px;
    border-radius: {r}px;
    border: 1px solid {c['bubble_ubrd']};
}}

/* Нижние кнопки */
QPushButton#mid_btn {{
    font-family: '{f}';
    font-size: 16px;
    padding: 0px;
    border-radius: {r}px;
    border: 1px solid {c['bubble_ubrd']};
}}
QPushButton#mid_btn:hover {{
    background-color: {c['btn_hover']};
}}

QPushButton#mic_btn {{
    font-family: '{f}';
    font-size: 17px;
    padding: 0px;
    border-radius: {r}px;
    border: 1px solid {c['bubble_ubrd']};
}}
QPushButton#mic_btn:hover {{
    background-color: #6a2020;
    border-color: #8a4040;
    color: #ffaaaa;
}}
QPushButton#mic_btn:pressed {{
    background-color: #8a1a1a;
    color: #ffffff;
}}

/* Диалог настроек */
QDialog {{
    background-color: {c['bg']};
}}
QWidget#settings_title_bar {{
    background-color: {c['toolbar_bg']};
}}
QLabel#settings_title {{
    font-size: 15px;
    color: {c['text']};
}}
QWidget#settings_body {{
    background-color: {c['bg']};
}}
QLabel#settings_row_label {{
    font-size: 13px;
    color: {c['text']};
}}
QLineEdit#settings_field {{
    background-color: {c['input_bg']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    padding: 0px 8px;
    font-size: 13px;
}}
QLineEdit#settings_field:focus {{
    border-color: {c['bubble_ubrd']};
}}
QWidget#settings_tab_bar {{
    background-color: {c['bg']};
}}
QPushButton#tab_btn {{
    background-color: transparent;
    border: none;
    border-radius: {r}px;
    padding: 2px 12px;
    font-size: 13px;
    color: {c['dim_text']};
}}
QPushButton#tab_btn:checked {{
    background-color: {c['btn_hover']};
    color: {c['text']};
}}
QPushButton#tab_btn:hover:!checked {{
    color: {c['text']};
}}
QWidget#settings_footer {{
    background-color: {c['toolbar_bg']};
}}
QPushButton#settings_save_btn {{
    background-color: {c['btn_hover']};
    font-weight: bold;
}}

/* Строка статуса */
QWidget#status_bar {{
    background-color: {c['toolbar_bg']};
}}
QLabel#status_left {{
    font-size: 11px;
    color: {c['status_text']};
}}
QLabel#status_right {{
    font-size: 11px;
    color: {c['dim_text']};
}}
"""
