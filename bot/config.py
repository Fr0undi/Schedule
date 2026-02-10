"""Конфигурация приложения через переменные окружения"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: list[int]
    GROUP_CHAT_ID: int
    WEBAPP_BASE_URL: str
    DATA_DIR: str = "data"
    NOTIFY_HOUR: int = 20
    NOTIFY_MINUTE: int = 0
    TIMEZONE: str = "Europe/Moscow"
    SEMESTER_START: str = "2025-02-03"
    GROUP_NAME: str = "Д-Э 310"

    class Config:
        env_file = ".env"


settings = Settings()
