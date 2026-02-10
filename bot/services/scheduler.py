"""Планировщик ежедневной рассылки расписания в групповой чат"""

from datetime import date, timedelta

from aiogram import Bot

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import get_day_schedule
from bot.services.week_utils import get_week_type
from bot.services.formatter import format_day_schedule

from bot.keyboards.inline import webapp_keyboard


logger = get_logger(__name__)


async def send_daily_schedule(bot: Bot) -> None:
    """Отправить расписание на завтра в групповой чат"""

    try:
        tomorrow = date.today() + timedelta(days=1)
        weekday = tomorrow.weekday()

        if weekday == 6:
            await bot.send_message(
                settings.GROUP_CHAT_ID,
                "🎉 Завтра воскресенье! Отдыхайте",
            )
            return

        week_type = get_week_type(tomorrow, settings.SEMESTER_START)
        lessons = get_day_schedule(weekday, week_type)

        if weekday == 5 and not lessons:
            await bot.send_message(
                settings.GROUP_CHAT_ID,
                "🎉 Завтра суббота без пар! Отдыхайте",
            )
            return

        text = format_day_schedule(lessons, tomorrow, settings.SEMESTER_START)

        markup = None
        if settings.WEBAPP_BASE_URL.startswith("https://"):
            markup = webapp_keyboard(settings.WEBAPP_BASE_URL, week_type)

        await bot.send_message(
            settings.GROUP_CHAT_ID,
            text,
            reply_markup=markup,
        )
        logger.info("Расписание на завтра отправлено в чат")

    except Exception:
        logger.exception("Ошибка при отправке расписания")


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
