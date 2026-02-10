"""Обработчики команд бота"""

from datetime import date, timedelta

from aiogram import Router

from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import get_day_schedule, get_full_schedule
from bot.services.week_utils import get_week_type
from bot.services.formatter import format_day_schedule, format_week_overview

from bot.keyboards.inline import webapp_keyboard, url_keyboard


logger = get_logger(__name__)

router = Router()


async def _send(message: Message, text: str, week_type: str) -> None:
    """Отправить с WebApp-кнопкой, при ошибке — без неё"""

    if settings.WEBAPP_BASE_URL.startswith("https://"):
        try:
            await message.answer(
                text,
                reply_markup=webapp_keyboard(settings.WEBAPP_BASE_URL, week_type),
            )
            return
        except TelegramBadRequest:
            logger.warning("WebApp-кнопка не прошла, отправляю URL-кнопку")
            await message.answer(
                text,
                reply_markup=url_keyboard(settings.WEBAPP_BASE_URL, week_type),
            )
            return
    await message.answer(text)


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    today = date.today()
    week_type = get_week_type(today, settings.SEMESTER_START)
    lessons = get_day_schedule(today.weekday(), week_type)
    text = format_day_schedule(lessons, today, settings.SEMESTER_START)
    await _send(message, text, week_type)


@router.message(Command("tomorrow"))
async def cmd_tomorrow(message: Message) -> None:
    tomorrow = date.today() + timedelta(days=1)
    week_type = get_week_type(tomorrow, settings.SEMESTER_START)
    lessons = get_day_schedule(tomorrow.weekday(), week_type)
    text = format_day_schedule(lessons, tomorrow, settings.SEMESTER_START)
    await _send(message, text, week_type)


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    today = date.today()
    week_type = get_week_type(today, settings.SEMESTER_START)
    full = get_full_schedule(week_type)
    text = format_week_overview(full, week_type, settings.SEMESTER_START, today)
    await _send(message, text, week_type)


@router.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "📚 <b>Бот расписания группы {group}</b>\n\n"
        "/today — расписание на сегодня\n"
        "/tomorrow — расписание на завтра\n"
        "/week — обзор на неделю\n"
        "/help — эта справка"
    ).format(group = settings.GROUP_NAME)
    await message.answer(text)
