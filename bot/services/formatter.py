"""Форматирование расписания в текстовые сообщения для Telegram"""

from datetime import date

from bot.services.week_utils import get_week_number, get_week_type, get_week_type_display

DAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

MONTHS_GENITIVE = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

NUM_EMOJI = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]

TYPE_EMOJI = {
    "Лекция": "📘",
    "Практика": "📕",
    "Лабораторная": "📗",
}

LESSON_TIMES: dict[int, tuple[str, str]] = {
    1: ("09:00", "10:35"),
    2: ("10:55", "12:30"),
    3: ("13:00", "14:35"),
    4: ("14:55", "16:30"),
    5: ("16:50", "18:25"),
    6: ("18:30", "20:05"),
    7: ("20:15", "21:50"),
}


def format_day_schedule(
    lessons: list[dict],
    target_date: date,
    semester_start: str,
) -> str:
    """Сформировать текст расписания на один день"""

    weekday = target_date.weekday()

    if weekday == 6:
        return "🎉 Выходной! Отдыхаем!"

    day_name = DAY_NAMES[weekday]
    day_str = f"{target_date.day} {MONTHS_GENITIVE[target_date.month]}"
    week_type = get_week_type(target_date, semester_start)
    week_num = get_week_number(target_date, semester_start)
    week_display = get_week_type_display(week_type)

    lines = [
        f"📅 <b>Расписание на {day_name}, {day_str}</b>",
        f"📆 {week_display} ({week_num}-я неделя)",
        "",
    ]

    if not lessons:
        lines.append("🎉 Пар нет, отдыхаем!")
        return "\n".join(lines)

    # Показываем окна между парами
    lesson_nums = {l["lesson_number"] for l in lessons}
    min_num = min(lesson_nums)
    max_num = max(lesson_nums)

    for num in range(min_num, max_num + 1):
        matching = [l for l in lessons if l["lesson_number"] == num]

        if not matching:
            emoji_num = NUM_EMOJI[num] if num < len(NUM_EMOJI) else f"{num}."
            t_start, t_end = LESSON_TIMES.get(num, ("??:??", "??:??"))
            lines.append(f"{emoji_num} {t_start} – {t_end}")
            lines.append(f"   🕐 <b>Окно</b>")
            lines.append("")
            continue

        for lesson in matching:
            emoji_num = NUM_EMOJI[num] if num < len(NUM_EMOJI) else f"{num}."
            type_emoji = TYPE_EMOJI.get(lesson["lesson_type"], "📙")

            lines.append(
                f"{emoji_num} {lesson['time_start']} – {lesson['time_end']}"
            )

            lines.append(f"   {type_emoji} <b>{lesson['subject']}</b>")

            details = []
            if lesson["lesson_type"]:
                details.append(lesson["lesson_type"])
            if lesson.get("teacher"):
                details.append(lesson["teacher"])
            if lesson.get("room"):
                details.append(f"ауд. {lesson['room']}")

            if details:
                lines.append(f"   {' - '.join(details)}")

            lines.append("")

    return "\n".join(lines).rstrip()


def format_week_overview(
    full_schedule: dict[int, list[dict]],
    week_type: str,
    semester_start: str,
    target_date: date,
) -> str:
    """Краткий обзор на неделю: сколько пар в каждый день"""

    week_num = get_week_number(target_date, semester_start)
    week_display = get_week_type_display(week_type)

    lines = [
        f"📋 <b>Обзор на неделю</b>",
        f"📆 {week_display} ({week_num}-я неделя)",
        "",
    ]

    for day in range(6):
        day_name = DAY_NAMES[day]
        lessons = full_schedule.get(day, [])
        count = len(lessons)

        if count == 0:
            lines.append(f"  {day_name}: выходной 🎉")
        else:
            word = _lesson_word(count)
            first_time = lessons[0]["time_start"]
            last_time = lessons[-1]["time_end"]
            lines.append(f"  {day_name}: {count} {word} ({first_time}–{last_time})")

    return "\n".join(lines)


def _lesson_word(n: int) -> str:
    """Склонение слова 'пара'"""

    if 11 <= n % 100 <= 19:
        return "пар"
    last = n % 10
    if last == 1:
        return "пара"
    if 2 <= last <= 4:
        return "пары"
    return "пар"
