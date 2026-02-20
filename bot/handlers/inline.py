"""Inline-режим: поиск расписания групп и преподавателей из любого чата"""

import re
import hashlib

from datetime import date
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
    _lesson_word, LESSON_TIMES,
)


router = Router()

_MAX_RESULTS = 50


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-]+", "", text).lower()


def _make_id(name: str) -> str:
    return hashlib.md5(name.encode()).hexdigest()


def _description_for_lessons(lessons: list[dict]) -> str:
    """Краткое описание: '3 пары (09:00–14:35)' или 'Нет пар сегодня'"""

    if not lessons:
        return "Нет пар сегодня"
    count = len(lessons)
    first = lessons[0]["time_start"]
    last = lessons[-1]["time_end"]
    return f"{count} {_lesson_word(count)} сегодня ({first}–{last})"


def _webapp_url(group_name: str | None = None, teacher_name: str | None = None, week_type: str = "odd") -> str:
    base = settings.WEBAPP_BASE_URL
    if teacher_name:
        return f"{base}/teachers?week={week_type}&name={quote(teacher_name)}"
    return f"{base}?week={week_type}&group={quote(group_name)}"


@router.inline_query()
async def on_inline_query(query: InlineQuery) -> None:
    text = query.query.strip()
    if not text or len(text) < 2:
        await query.answer([], cache_time = 5, is_personal = False)
        return

    query_lower = text.lower()
    query_norm = _normalize(text)

    today = date.today()
    weekday = today.weekday() + 1  # 1=Mon .. 7=Sun
    week_type = get_week_type(today, settings.SEMESTER_START)

    results: list[InlineQueryResultArticle] = []

    # Search groups
    for name in list_available_groups():
        if query_lower not in name.lower() and query_norm not in _normalize(name):
            continue

        lessons = get_day_schedule(name, weekday, week_type) if weekday <= 6 else []
        msg_text = format_day_schedule(lessons, today, settings.SEMESTER_START)
        msg_text = f"📚 <b>{name}</b>\n\n{msg_text}"

        kb = None
        if settings.WEBAPP_BASE_URL.startswith("https://"):
            kb = InlineKeyboardMarkup(inline_keyboard = [[
                InlineKeyboardButton(
                    text = "📱 Полное расписание",
                    url = _webapp_url(group_name = name, week_type = week_type),
                )
            ]])

        results.append(InlineQueryResultArticle(
            id = _make_id(f"g:{name}"),
            title = f"📚 {name}",
            description = _description_for_lessons(lessons),
            input_message_content = InputTextMessageContent(
                message_text = msg_text,
                parse_mode = "HTML",
            ),
            reply_markup = kb,
        ))

        if len(results) >= _MAX_RESULTS:
            break

    # Search teachers (if still room)
    if len(results) < _MAX_RESULTS:
        for name in list_available_teachers():
            if query_lower not in name.lower() and query_norm not in _normalize(name):
                continue

            lessons = get_teacher_day_schedule(name, weekday, week_type) if weekday <= 6 else []
            msg_text = format_teacher_day_schedule(lessons, today, settings.SEMESTER_START)
            msg_text = f"👨\u200d🏫 <b>{name}</b>\n\n{msg_text}"

            kb = None
            if settings.WEBAPP_BASE_URL.startswith("https://"):
                kb = InlineKeyboardMarkup(inline_keyboard = [[
                    InlineKeyboardButton(
                        text = "📱 Полное расписание",
                        url = _webapp_url(teacher_name = name, week_type = week_type),
                    )
                ]])

            results.append(InlineQueryResultArticle(
                id = _make_id(f"t:{name}"),
                title = f"👨\u200d🏫 {name}",
                description = _description_for_lessons(lessons),
                input_message_content = InputTextMessageContent(
                    message_text = msg_text,
                    parse_mode = "HTML",
                ),
                reply_markup = kb,
            ))

            if len(results) >= _MAX_RESULTS:
                break

    await query.answer(results, cache_time = 60, is_personal = False)
