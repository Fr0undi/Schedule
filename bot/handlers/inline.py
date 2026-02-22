"""Inline-режим: поиск расписания групп и преподавателей из любого чата"""

import re
import hashlib

from datetime import date, timedelta
from urllib.parse import quote

from aiogram import Router
from aiogram.types import (
    InlineQuery, InlineQueryResultArticle,
    InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.config import settings

from bot.services.storage import (
    list_available_groups, list_available_teachers,
    get_day_schedule, get_teacher_day_schedule,
)
from bot.services.week_utils import get_week_type
from bot.services.formatter import (
    format_day_schedule, format_teacher_day_schedule,
    _lesson_word, DAY_NAMES,
)


router = Router()

_MAX_RESULTS = 50


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-]+", "", text).lower()


def _make_id(name: str) -> str:
    return hashlib.md5(name.encode()).hexdigest()


def _description_for_lessons(lessons: list[dict], label: str) -> str:
    """Краткое описание: '3 пары (09:00–14:35)' или 'Нет пар'"""

    if not lessons:
        return f"Нет пар {label}"
    count = len(lessons)
    first = lessons[0]["time_start"]
    last = lessons[-1]["time_end"]
    return f"{count} {_lesson_word(count)} {label} ({first}–{last})"


def _webapp_url(group_name: str | None = None, teacher_name: str | None = None, week_type: str = "odd") -> str:
    base = settings.WEBAPP_BASE_URL
    if teacher_name:
        return f"{base}/teachers?week={week_type}&name={quote(teacher_name)}"
    return f"{base}?week={week_type}&group={quote(group_name)}"


def _kb(group_name: str | None = None, teacher_name: str | None = None, week_type: str = "odd") -> InlineKeyboardMarkup | None:
    if not settings.WEBAPP_BASE_URL.startswith("https://"):
        return None
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            url = _webapp_url(group_name = group_name, teacher_name = teacher_name, week_type = week_type),
        )
    ]])


def _day_label(target: date) -> str:
    """'сегодня (Среда)' или 'завтра (Четверг)'"""

    today = date.today()
    wd = target.weekday()
    if wd >= 6:
        return ""
    name = DAY_NAMES[wd]
    if target == today:
        return f"сегодня ({name})"
    return f"завтра ({name})"


@router.inline_query()
async def on_inline_query(query: InlineQuery) -> None:
    text = query.query.strip()
    if not text or len(text) < 2:
        await query.answer([], cache_time = 5, is_personal = False)
        return

    query_lower = text.lower()
    query_norm = _normalize(text)

    today = date.today()
    tomorrow = today + timedelta(days = 1)

    days = []  # (target_date, suffix_id, label_short)
    if today.weekday() < 6:
        days.append((today, "today", "сегодня"))
    if tomorrow.weekday() < 6:
        days.append((tomorrow, "tmrw", "завтра"))

    results: list[InlineQueryResultArticle] = []

    # Search groups
    for name in list_available_groups():
        if query_lower not in name.lower() and query_norm not in _normalize(name):
            continue

        for target, suffix, short in days:
            weekday = target.weekday() + 1
            wt = get_week_type(target, settings.SEMESTER_START)
            lessons = get_day_schedule(name, weekday, wt)
            msg_text = format_day_schedule(lessons, target, settings.SEMESTER_START)
            msg_text = f"📚 <b>{name}</b>\n\n{msg_text}"

            label = _day_label(target)

            results.append(InlineQueryResultArticle(
                id = _make_id(f"g:{name}:{suffix}"),
                title = f"📚 {name} — {short}",
                description = _description_for_lessons(lessons, label),
                input_message_content = InputTextMessageContent(
                    message_text = msg_text,
                    parse_mode = "HTML",
                ),
                reply_markup = _kb(group_name = name, week_type = wt),
            ))

        if len(results) >= _MAX_RESULTS:
            break

    # Search teachers
    if len(results) < _MAX_RESULTS:
        for name in list_available_teachers():
            if query_lower not in name.lower() and query_norm not in _normalize(name):
                continue

            for target, suffix, short in days:
                weekday = target.weekday() + 1
                wt = get_week_type(target, settings.SEMESTER_START)
                lessons = get_teacher_day_schedule(name, weekday, wt)
                msg_text = format_teacher_day_schedule(lessons, target, settings.SEMESTER_START)
                msg_text = f"👨\u200d🏫 <b>{name}</b>\n\n{msg_text}"

                label = _day_label(target)

                results.append(InlineQueryResultArticle(
                    id = _make_id(f"t:{name}:{suffix}"),
                    title = f"👨\u200d🏫 {name} — {short}",
                    description = _description_for_lessons(lessons, label),
                    input_message_content = InputTextMessageContent(
                        message_text = msg_text,
                        parse_mode = "HTML",
                    ),
                    reply_markup = _kb(teacher_name = name, week_type = wt),
                ))

            if len(results) >= _MAX_RESULTS:
                break

    await query.answer(results, cache_time = 60, is_personal = False)
