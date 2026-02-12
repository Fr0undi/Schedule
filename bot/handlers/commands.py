"""Обработчики команд бота: /today, /tomorrow, /week, /help"""

from datetime import date, timedelta

from aiogram import Router

from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import get_day_schedule, get_full_schedule, get_group_by_chat
from bot.services.week_utils import get_week_type
from bot.services.formatter import format_day_schedule, format_week_overview

from bot.keyboards.inline import webapp_keyboard, url_keyboard


logger = get_logger(__name__)

router = Router()


NOT_REGISTERED = "❓ Группа не привязана к этому чату\nИспользуйте /register для привязки"


def _get_group(chat_id: int) -> dict | None:
    """Получить конфиг группы по chat_id"""

    return get_group_by_chat(chat_id)


async def _send(message: Message, text: str, week_type: str, group_name: str) -> None:
    """Отправить с WebApp-кнопкой, при ошибке — без неё"""

    if settings.WEBAPP_BASE_URL.startswith("https://"):
        try:
            await message.answer(
                text,
                reply_markup = webapp_keyboard(settings.WEBAPP_BASE_URL, week_type, group_name),
            )
            return
        except TelegramBadRequest:
            logger.warning("WebApp-кнопка не прошла, отправляю URL-кнопку")
            await message.answer(
                text,
                reply_markup = url_keyboard(settings.WEBAPP_BASE_URL, week_type, group_name),
            )
            return
    await message.answer(text)


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    group = _get_group(message.chat.id)
    if not group:
        await message.answer(NOT_REGISTERED)
        return

    today = date.today()
    week_type = get_week_type(today, group["semester_start"])
    lessons = get_day_schedule(group["group_name"], today.weekday(), week_type)
    text = format_day_schedule(lessons, today, group["semester_start"])
    await _send(message, text, week_type, group["group_name"])


@router.message(Command("tomorrow"))
async def cmd_tomorrow(message: Message) -> None:
    group = _get_group(message.chat.id)
    if not group:
        await message.answer(NOT_REGISTERED)
        return

    tomorrow = date.today() + timedelta(days = 1)
    week_type = get_week_type(tomorrow, group["semester_start"])
    lessons = get_day_schedule(group["group_name"], tomorrow.weekday(), week_type)
    text = format_day_schedule(lessons, tomorrow, group["semester_start"])
    await _send(message, text, week_type, group["group_name"])


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    group = _get_group(message.chat.id)
    if not group:
        await message.answer(NOT_REGISTERED)
        return

    today = date.today()
    week_type = get_week_type(today, group["semester_start"])
    full = get_full_schedule(group["group_name"], week_type)
    text = format_week_overview(full, week_type, group["semester_start"], today)
    await _send(message, text, week_type, group["group_name"])


@router.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    group = _get_group(message.chat.id)
    group_name = group["group_name"] if group else "не привязана"

    text = (
        f"📚 <b>Бот расписания</b> (группа: {group_name})\n\n"
        "/today — расписание на сегодня\n"
        "/tomorrow — расписание на завтра\n"
        "/week — обзор на неделю\n"
        "/register — привязать группу к чату\n"
        "/unregister — отвязать группу\n"
        "/help — эта справка"
    )
    await message.answer(text)
