"""Хранение и загрузка расписания в формате JSON"""

import json

from pathlib import Path
from datetime import datetime

from bot.config import settings

from bot.logger import get_logger


logger = get_logger(__name__)


SCHEDULE_PATH = Path(settings.DATA_DIR) / "schedule.json"


def save_schedule(lessons: list[dict]) -> None:
    """Сохранить распарсенное расписание"""

    data = {
        "updated_at": datetime.now().isoformat(),
        "lessons": lessons,
    }
    SCHEDULE_PATH.parent.mkdir(parents = True, exist_ok = True)
    SCHEDULE_PATH.write_text(json.dumps(data, ensure_ascii = False, indent = 2), encoding = "utf-8")
    logger.info("Расписание сохранено: %d пар", len(lessons))


def load_schedule() -> list[dict]:
    """Загрузить расписание, пустой список если файла нет"""

    if not SCHEDULE_PATH.exists():
        return []
    try:
        data = json.loads(SCHEDULE_PATH.read_text(encoding = "utf-8"))
        return data.get("lessons", [])
    except Exception:
        logger.exception("Ошибка чтения schedule.json")
        return []


def get_day_schedule(weekday: int, week_type: str) -> list[dict]:
    """Получить пары на конкретный день с учётом типа недели"""

    lessons = load_schedule()
    return sorted(
        [
            l for l in lessons
            if l["weekday"] == weekday
            and l["week_type"] in ("both", week_type)
        ],
        key=lambda l: l["lesson_number"],
    )


def get_full_schedule(week_type: str) -> dict[int, list[dict]]:
    """Всё расписание, сгруппированное по дням (для WebApp)"""

    lessons = load_schedule()
    result: dict[int, list[dict]] = {}
    for day in range(6):  # Пн-Сб
        day_lessons = sorted(
            [
                l for l in lessons
                if l["weekday"] == day
                and l["week_type"] in ("both", week_type)
            ],
            key=lambda l: l["lesson_number"],
        )
        if day_lessons:
            result[day] = day_lessons
    return result
