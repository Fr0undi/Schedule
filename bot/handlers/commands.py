"""Обработчики команд бота: /today, /tomorrow, /week, /help"""

from datetime import date, timedelta

from aiogram import F, Router

from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import (
    get_day_schedule, get_full_schedule, get_group_by_chat, save_topic,
    get_teacher_day_schedule, get_teacher_full_schedule,
)
from bot.services.week_utils import get_week_type
from bot.services.formatter import format_day_schedule, format_teacher_day_schedule, format_week_overview

from bot.keyboards.inline import (
    webapp_keyboard, url_keyboard,
    teacher_webapp_keyboard, teacher_url_keyboard,
)
from bot.keyboards.reply_kb import main_keyboard


logger = get_logger(__name__)

router = Router()


NOT_REGISTERED = "❓ Расписание не привязано к этому чату\nИспользуйте /register для привязки"


def _get_group(chat_id: int) -> dict | None:
    """Получить конфиг группы по chat_id"""

    return get_group_by_chat(chat_id)


async def _send(
    message: Message, text: str, week_type: str,
    group_name: str | None = None, teacher_name: str | None = None,
) -> None:
    """Отправить с WebApp-кнопкой, при ошибке — без неё"""

    if settings.WEBAPP_BASE_URL.startswith("https://"):
        if teacher_name:
            kb = teacher_webapp_keyboard(settings.WEBAPP_BASE_URL, week_type, teacher_name)
            fallback_kb = teacher_url_keyboard(settings.WEBAPP_BASE_URL, week_type, teacher_name)
        else:
            kb = webapp_keyboard(settings.WEBAPP_BASE_URL, week_type, group_name)
            fallback_kb = url_keyboard(settings.WEBAPP_BASE_URL, week_type, group_name)
        try:
            await message.answer(text, reply_markup = kb)
            return
        except TelegramBadRequest:
            logger.warning("WebApp-кнопка не прошла, отправляю URL-кнопку")
            await message.answer(text, reply_markup = fallback_kb)
            return
    await message.answer(text)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    group = _get_group(message.chat.id)
    kb = main_keyboard() if message.chat.type == "private" else None

    if group:
        bound = group.get("teacher_name") or group.get("group_name", "")
        label = "Преподаватель" if group.get("teacher_name") else "Группа"
        await message.answer(
            f"👋 Привет! Я бот расписания РГАУ-МСХА\n\n"
            f"{label}: <b>{bound}</b>\n\n"
            "📅 /today — расписание на сегодня\n"
            "📅 /tomorrow — расписание на завтра\n"
            "📆 /week — обзор на неделю\n"
            "✏️ /edit — редактировать расписание\n"
            "📋 /register — сменить привязку\n"
            "📖 /help — все команды",
            reply_markup = kb,
        )
    else:
        await message.answer(
            "👋 Привет! Я бот расписания РГАУ-МСХА\n\n"
            "Чтобы начать, привяжите группу или преподавателя:\n"
            "/register — выбрать",
            reply_markup = kb,
        )


@router.message(F.chat.type == "private", F.text == "📅 Сегодня")
@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    group = _get_group(message.chat.id)
    if not group:
        await message.answer(NOT_REGISTERED)
        return

    today = date.today()
    week_type = get_week_type(today, group["semester_start"])

    if group.get("teacher_name"):
        teacher = group["teacher_name"]
        lessons = get_teacher_day_schedule(teacher, today.weekday() + 1, week_type)
        text = format_teacher_day_schedule(lessons, today, group["semester_start"])
        await _send(message, text, week_type, teacher_name = teacher)
    else:
        gname = group["group_name"]
        lessons = get_day_schedule(gname, today.weekday() + 1, week_type)
        text = format_day_schedule(lessons, today, group["semester_start"])
        await _send(message, text, week_type, group_name = gname)


@router.message(F.chat.type == "private", F.text == "📅 Завтра")
@router.message(Command("tomorrow"))
async def cmd_tomorrow(message: Message) -> None:
    group = _get_group(message.chat.id)
    if not group:
        await message.answer(NOT_REGISTERED)
        return

    tomorrow = date.today() + timedelta(days = 1)
    week_type = get_week_type(tomorrow, group["semester_start"])

    if group.get("teacher_name"):
        teacher = group["teacher_name"]
        lessons = get_teacher_day_schedule(teacher, tomorrow.weekday() + 1, week_type)
        text = format_teacher_day_schedule(lessons, tomorrow, group["semester_start"])
        await _send(message, text, week_type, teacher_name = teacher)
    else:
        gname = group["group_name"]
        lessons = get_day_schedule(gname, tomorrow.weekday() + 1, week_type)
        text = format_day_schedule(lessons, tomorrow, group["semester_start"])
        await _send(message, text, week_type, group_name = gname)


@router.message(F.chat.type == "private", F.text == "📆 Неделя")
@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    group = _get_group(message.chat.id)
    if not group:
        await message.answer(NOT_REGISTERED)
        return

    today = date.today()
    week_type = get_week_type(today, group["semester_start"])

    if group.get("teacher_name"):
        teacher = group["teacher_name"]
        full = get_teacher_full_schedule(teacher, week_type)
        text = format_week_overview(full, week_type, group["semester_start"], today)
        await _send(message, text, week_type, teacher_name = teacher)
    else:
        gname = group["group_name"]
        full = get_full_schedule(gname, week_type)
        text = format_week_overview(full, week_type, group["semester_start"], today)
        await _send(message, text, week_type, group_name = gname)


@router.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>")


@router.message(Command("settopic"))
async def cmd_settopic(message: Message) -> None:
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в группах с темами")
        return

    topic_id = message.message_thread_id
    if not topic_id:
        # Написано в General или группа без тем — сбросить привязку
        if save_topic(message.chat.id, None):
            await message.answer("✅ Рассылка будет приходить в основной чат (без темы)")
        else:
            await message.answer(NOT_REGISTERED)
        return

    if save_topic(message.chat.id, topic_id):
        await message.answer("✅ Ежедневная рассылка будет приходить в эту тему")
    else:
        await message.answer(NOT_REGISTERED)


@router.message(F.chat.type == "private", F.text == "❓ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    group = _get_group(message.chat.id)
    if group:
        bound = group.get("teacher_name") or group.get("group_name", "")
    else:
        bound = "не привязано"

    text = (
        f"📚 <b>Бот расписания</b> ({bound})\n\n"
        "/today — расписание на сегодня\n"
        "/tomorrow — расписание на завтра\n"
        "/week — обзор на неделю\n"
        "/edit — редактировать расписание\n"
        "/register — привязать группу/преподавателя\n"
        "/unregister — отвязать\n"
        "/settopic — рассылка в эту тему\n"
        "/help — эта справка"
    )
    kb = main_keyboard() if message.chat.type == "private" else None
    await message.answer(text, reply_markup = kb)
