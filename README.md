# Grok Agent

AI-ассистент на базе xAI Grok API с графическим интерфейсом на PySide6.
Серия YouTube "AI помощник своими руками" — github.com/mirashic33-alt/grok-agent

---

## Что умеет

- Чат с моделями Grok (grok-4.1, grok-4.3, grok-4.20)
- Голосовой ввод через микрофон (Vosk STT, push-to-talk)
- Озвучка ответов (xAI TTS, несколько голосов)
- Поиск в интернете (встроен в Grok API)
- Прикрепление изображений и файлов
- Telegram-бот — отправлять запросы и получать ответы из мессенджера
- Мониторинг баланса xAI прямо в шапке приложения
- Генерация изображений, скриншоты, работа с файлами, запуск команд
- История чата, несколько тем оформления

---

## Установка

```bash
git clone https://github.com/mirashic33-alt/grok-agent.git
cd grok-agent
pip install -r requirements.txt
python main.pyw
```

Для голосового ввода дополнительно:
```bash
pip install vosk sounddevice
```
Модель Vosk (~45MB) скачивается автоматически при первом включении микрофона.

---

## Структура проекта

```
main.pyw                  — точка входа
│
├── ui/
│   ├── main_window.py    — главное окно, чат, вся логика интерфейса
│   ├── settings_dialog.py — диалог настроек (ключи, модель, голос, биллинг)
│   └── theme.py          — система тем, цвета, константы
│
├── core/
│   ├── message_worker.py — отправка запросов к Grok API в фоне
│   ├── stt.py            — Vosk STT: загрузка модели, потоковая транскрипция
│   ├── memory_loader.py  — загрузка файлов личности агента
│   └── daily_log.py      — журнал сообщений по дням
│
├── llm/
│   └── provider.py       — обёртка над xAI API (OpenAI-совместимый)
│
├── data/
│   ├── config.py         — настройки приложения (config.json)
│   ├── keystore.py       — зашифрованное хранилище ключей (keys.enc)
│   ├── chat_history.py   — история переписки
│   ├── billing.py        — запрос баланса через xAI Management API
│   └── token_log.py      — счётчик токенов за сессию
│
├── tools/
│   ├── tts.py            — озвучка через xAI TTS API
│   ├── file_tools.py     — чтение/запись файлов, поиск
│   ├── shell_tools.py    — выполнение команд оболочки
│   ├── image_tools.py    — генерация изображений, скриншоты
│   └── time_sense.py     — текущее время для агента
│
├── channels/
│   └── telegram/bot.py   — Telegram-бот (приём и отправка сообщений)
│
├── themes/               — JSON-файлы тем оформления
├── models/               — локальные STT-модели (в .gitignore)
└── workspace/            — личные файлы агента (в .gitignore)
```

---

## Настройка

Запусти приложение → кнопка шестерёнки → вкладка **Ключи**:

| Ключ | Где взять |
|---|---|
| Grok API Key | console.x.ai → API Keys |
| Telegram Bot Token | @BotFather в Telegram |
| Telegram Chat ID | @userinfobot |

Для мониторинга баланса — вкладка **Биллинг**:

| Ключ | Где взять |
|---|---|
| Management Key | console.x.ai → Settings → Management API |
| Team ID | console.x.ai → Settings (UUID команды) |

---

## Ключи и безопасность

Все ключи хранятся в `data/keys.enc` — зашифрованный файл, в репозиторий не попадает.
В `.gitignore` также исключены: история чатов, личные файлы агента, локальные модели STT.

---

## Темы оформления

Семь встроенных тем: dark, pink, red, green, ari_theme, theme_sand и другие.
Переключение — кнопка палитры в шапке приложения.
Каждая тема — JSON-файл в папке `themes/`, легко создать свою.

---

## YouTube-серия

Проект создаётся в прямом эфире на YouTube-канале.
Каждый шаг — отдельное видео, от нуля до полноценного агента.

- Шаг 1 — Первый запрос к Grok API
- Шаг 2 — Инструменты: файлы, скриншоты, генерация картинок, Telegram
- Шаг 3 — Биллинг, TTS-озвучка, тюнинг интерфейса
- Шаг 4 — Голосовой ввод (Vosk STT, push-to-talk)
