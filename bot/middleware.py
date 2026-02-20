"""Middleware для логирования использования команд"""

import json

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.config import settings
from bot.logger import get_logger


logger = get_logger(__name__)

_MSK = timezone(timedelta(hours = 3))
_LOG_PATH = Path(settings.DATA_DIR) / "commands_log.jsonl"


class CommandLogMiddleware(BaseMiddleware):
    """Записывает каждую команду бота в JSONL-файл и в stdout"""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.text and event.text.startswith("/"):
            command = event.text.split()[0].split("@")[0]  # /register@botname → /register
            user = event.from_user
            username = f"@{user.username}" if user and user.username else str(user.id if user else "?")
            entry = {
                "command": command,
                "user_id": user.id if user else None,
                "username": user.username if user else None,
                "chat_id": event.chat.id,
                "chat_type": event.chat.type,
                "timestamp": datetime.now(_MSK).isoformat(),
            }

            logger.info(
                "Команда %s от %s в чате %d (%s)",
                command, username, event.chat.id, event.chat.type,
            )

            _LOG_PATH.parent.mkdir(parents = True, exist_ok = True)
            with open(_LOG_PATH, "a", encoding = "utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii = False) + "\n")

        return await handler(event, data)
