"""Планировщик ежедневной рассылки расписания во все зарегистрированные чаты"""

from datetime import date, timedelta

from aiogram import Bot

from aiogram.exceptions import TelegramBadRequest

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import get_day_schedule, load_groups
from bot.services.week_utils import get_week_type
from bot.services.formatter import format_day_schedule

from bot.keyboards.inline import webapp_keyboard, url_keyboard


logger = get_logger(__name__)


async def _send_to_chat(bot: Bot, chat_id: int, text: str, week_type: str, group_name: str) -> None:
    """Отправить сообщение в чат с фоллбэком кнопки"""

    if settings.WEBAPP_BASE_URL.startswith("https://"):
        try:
            await bot.send_message(
                chat_id, text,
                reply_markup = webapp_keyboard(settings.WEBAPP_BASE_URL, week_type, group_name),
            )
            return
        except TelegramBadRequest:
            logger.warning("WebApp-кнопка не прошла для чата %d, отправляю URL-кнопку", chat_id)
            await bot.send_message(
                chat_id, text,
                reply_markup = url_keyboard(settings.WEBAPP_BASE_URL, week_type, group_name),
            )
            return
    await bot.send_message(chat_id, text)


async def send_daily_schedule(bot: Bot) -> None:
    """Отправить расписание на завтра во все зарегистрированные чаты"""

    groups = load_groups()
    if not groups:
        logger.info("Нет зарегистрированных групп, пропускаю рассылку")
        return

    tomorrow = date.today() + timedelta(days = 1)
    weekday = tomorrow.weekday() + 1
    logger.info("Рассылка: завтра %s, weekday=%d, групп=%d", tomorrow, weekday, len(groups))

    for chat_id, group_config in groups.items():
        group_name = group_config["group_name"]
        semester_start = group_config["semester_start"]

        try:
            if weekday == 7:
                await bot.send_message(chat_id, "🎉 Завтра воскресенье! Отдыхайте")
                continue

            week_type = get_week_type(tomorrow, semester_start)
            lessons = get_day_schedule(group_name, weekday, week_type)

            if weekday == 6 and not lessons:
                await bot.send_message(chat_id, "🎉 Завтра суббота без пар! Отдыхайте")
                continue

            text = format_day_schedule(lessons, tomorrow, semester_start)
            await _send_to_chat(bot, chat_id, text, week_type, group_name)
            logger.info("Расписание отправлено в чат %d [%s]", chat_id, group_name)

        except Exception:
            logger.exception("Ошибка при отправке в чат %d [%s]", chat_id, group_name)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Настроить планировщик ежедневной рассылки"""

    scheduler = AsyncIOScheduler(timezone = settings.TIMEZONE)
    scheduler.add_job(
        send_daily_schedule,
        CronTrigger(
            hour = settings.NOTIFY_HOUR,
            minute = settings.NOTIFY_MINUTE,
            timezone = settings.TIMEZONE,
        ),
        args = [bot],
        id = "daily_schedule",
        replace_existing = True,
    )
    logger.info(
        "Планировщик настроен: %02d:%02d %s",
        settings.NOTIFY_HOUR, settings.NOTIFY_MINUTE, settings.TIMEZONE,
    )
    return scheduler
