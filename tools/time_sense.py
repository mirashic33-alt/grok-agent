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

    hour = now.hour
    if 6 <= hour < 12:
        period = "утро"
    elif 12 <= hour < 18:
        period = "день"
    elif 18 <= hour < 23:
        period = "вечер"
    else:
        period = "ночь"

    lines.append(
        f"Время суток: {period}. "
        "Реагируй на время как живой человек — коротко и к месту:\n"
        "— утром: «доброе утро» если пишет первый раз за день\n"
        "— вечером: можно заметить что уже вечер\n"
        "— ночью: скажи что поздно, особенно если это нетипично\n"
        "— большой перерыв (>3 часов): заметь что давно не писал\n"
        "— не штампуй одно и то же каждый раз, одно упоминание — и хватит"
    )

    return "\n".join(lines)
