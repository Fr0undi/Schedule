"""Планировщик ежедневной рассылки расписания во все зарегистрированные чаты"""

from datetime import date, timedelta

from aiogram import Bot

from aiogram.exceptions import TelegramBadRequest

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings

from bot.logger import get_logger

from bot.services.storage import get_day_schedule, get_teacher_day_schedule, load_groups
from bot.services.week_utils import get_week_type
from bot.services.formatter import format_day_schedule, format_teacher_day_schedule

from bot.keyboards.inline import (
    webapp_keyboard, url_keyboard,
    teacher_webapp_keyboard, teacher_url_keyboard,
)


logger = get_logger(__name__)


async def _send_to_chat(
    bot: Bot, chat_id: int, text: str,
    week_type: str,
    group_name: str | None = None,
    teacher_name: str | None = None,
    topic_id: int | None = None,
) -> None:
    """Отправить сообщение в чат с фоллбэком кнопки"""

    kwargs = {}
    if topic_id:
        kwargs["message_thread_id"] = topic_id

    if settings.WEBAPP_BASE_URL.startswith("https://"):
        if teacher_name:
            kb = teacher_webapp_keyboard(settings.WEBAPP_BASE_URL, week_type, teacher_name)
            fallback_kb = teacher_url_keyboard(settings.WEBAPP_BASE_URL, week_type, teacher_name)
        else:
            kb = webapp_keyboard(settings.WEBAPP_BASE_URL, week_type, group_name)
            fallback_kb = url_keyboard(settings.WEBAPP_BASE_URL, week_type, group_name)
        try:
            await bot.send_message(chat_id, text, reply_markup = kb, **kwargs)
            return
        except TelegramBadRequest:
            logger.warning("WebApp-кнопка не прошла для чата %d, отправляю URL-кнопку", chat_id)
            await bot.send_message(chat_id, text, reply_markup = fallback_kb, **kwargs)
            return
    await bot.send_message(chat_id, text, **kwargs)


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
        group_name = group_config.get("group_name")
        teacher_name = group_config.get("teacher_name")
        semester_start = group_config["semester_start"]
        topic_id = group_config.get("topic_id")
        bound_name = teacher_name or group_name or "?"

        kwargs = {}
        if topic_id:
            kwargs["message_thread_id"] = topic_id

        try:
            if weekday == 7:
                await bot.send_message(chat_id, "🎉 Завтра воскресенье! Отдыхайте", **kwargs)
                continue

            week_type = get_week_type(tomorrow, semester_start)

            if teacher_name:
                lessons = get_teacher_day_schedule(teacher_name, weekday, week_type)
            else:
                lessons = get_day_schedule(group_name, weekday, week_type)

            if weekday == 6 and not lessons:
                await bot.send_message(chat_id, "🎉 Завтра суббота без пар! Отдыхайте", **kwargs)
                continue

            if teacher_name:
                text = format_teacher_day_schedule(lessons, tomorrow, semester_start)
            else:
                text = format_day_schedule(lessons, tomorrow, semester_start)

            await _send_to_chat(
                bot, chat_id, text, week_type,
                group_name = group_name, teacher_name = teacher_name,
                topic_id = topic_id,
            )
            logger.info("Расписание отправлено в чат %d [%s]", chat_id, bound_name)

        except Exception:
            logger.exception("Ошибка при отправке в чат %d [%s]", chat_id, bound_name)


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
