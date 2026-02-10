"""Точка входа: запуск Telegram-бота и FastAPI-сервера"""

import asyncio
import uvicorn

from aiogram import Bot, Dispatcher

from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings

from bot.logger import setup_logging, get_logger

from bot.handlers import commands, upload

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

    # Подключаем роутеры
    dp.include_router(commands.router)
    dp.include_router(upload.router)

    # APScheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()

    # FastAPI (webapp) в фоне
    config = uvicorn.Config(webapp_app, host = "0.0.0.0", port = 8080, log_level = "info")
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())

    logger.info("Бот запущен. Группа: %s", settings.GROUP_NAME)

    # Polling
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
