"""
time_sense.py — даёт агенту ощущение времени.

Инжектируется в system prompt при каждом запросе — не в историю.
История остаётся чистой, время всегда актуальное.
"""

from datetime import datetime


_WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def get_time_block(last_message_ts: str | None = None, last_message_date: str | None = None) -> str:
    now     = datetime.now()
    weekday = _WEEKDAYS[now.weekday()]
    dt_str  = now.strftime(f"%d.%m.%Y, {weekday}, %H:%M")

    lines = [f"Сейчас: {dt_str}"]

    if last_message_ts and last_message_date:
        try:
            last_dt = datetime.strptime(f"{last_message_date} {last_message_ts}", "%Y-%m-%d %H:%M")
            minutes = int((now - last_dt).total_seconds() / 60)
            if minutes < 1:
                delta = "только что"
            elif minutes < 60:
                delta = f"{minutes} мин. назад"
            elif minutes < 1440:
                delta = f"{minutes // 60} ч. назад"
            else:
                delta = f"{minutes // 1440} дн. назад"
            lines.append(f"Предыдущее сообщение: {delta}")
        except Exception:
            pass

    lines.append(
        "Используй это для живой ориентации во времени. "
        "Не вставляй приветствие по времени суток в каждый ответ — "
        "но реагируй естественно: если человек пишет первый раз за день, "
        "если уже глубокая ночь, если прошло много времени с прошлого сообщения. "
        "Как живой собеседник, а не как часы."
    )

    return "\n".join(lines)
