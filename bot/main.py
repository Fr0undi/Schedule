"""Точка входа: запуск Telegram-бота и FastAPI-сервера"""

import asyncio
import uvicorn

from aiogram import Bot, Dispatcher

from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo, BotCommand

from bot.config import settings

from bot.logger import setup_logging, get_logger

from bot.handlers import commands, upload, register, edit_schedule

from bot.services.scheduler import setup_scheduler

from webapp.app import app as webapp_app


setup_logging()
logger = get_logger(__name__)


async def main() -> None:
    bot = Bot(
        token = settings.BOT_TOKEN,
        default = DefaultBotProperties(parse_mode = ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(commands.router)
    dp.include_router(upload.router)
    dp.include_router(register.router)
    dp.include_router(edit_schedule.router)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    config = uvicorn.Config(webapp_app, host = "0.0.0.0", port = 8080, log_level = "info")
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())

    # Зарегистрировать команды в меню Telegram
    await bot.set_my_commands([
        BotCommand(command = "today", description = "Расписание на сегодня"),
        BotCommand(command = "tomorrow", description = "Расписание на завтра"),
        BotCommand(command = "week", description = "Обзор на неделю"),
        BotCommand(command = "edit", description = "Редактировать расписание"),
        BotCommand(command = "register", description = "Привязать группу к чату"),
        BotCommand(command = "unregister", description = "Отвязать группу"),
        BotCommand(command = "settopic", description = "Рассылка в эту тему"),
        BotCommand(command = "help", description = "Справка"),
    ])
    logger.info("Команды бота зарегистрированы")

    # Установить кнопку меню (мини-приложение)
    if settings.WEBAPP_BASE_URL.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button = MenuButtonWebApp(
                text = "Расписание",
                web_app = WebAppInfo(url = settings.WEBAPP_BASE_URL),
            ),
        )
        logger.info("Menu button установлена: %s", settings.WEBAPP_BASE_URL)

    logger.info("Бот запущен")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
