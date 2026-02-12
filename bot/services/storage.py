"""Хранение и загрузка расписания в формате JSON"""

import json
import re

from pathlib import Path
from datetime import datetime

from bot.config import settings

from bot.logger import get_logger


logger = get_logger(__name__)

DATA_DIR = Path(settings.DATA_DIR)
SCHEDULES_DIR = DATA_DIR / "schedules"
GROUPS_PATH = DATA_DIR / "groups.json"


def _slugify(group_name: str) -> str:
    """Преобразовать название группы в безопасное имя файла"""

    return re.sub(r"[^\w\-]", "_", group_name).strip("_")


def _schedule_path(group_name: str) -> Path:
    """Путь к файлу расписания группы"""

    return SCHEDULES_DIR / f"{_slugify(group_name)}.json"


# --- Расписание ---

def save_schedule(group_name: str, lessons: list[dict]) -> None:
    """Сохранить расписание для конкретной группы"""

    data = {
        "updated_at": datetime.now().isoformat(),
        "lessons": lessons,
    }
    SCHEDULES_DIR.mkdir(parents = True, exist_ok = True)
    path = _schedule_path(group_name)
    path.write_text(json.dumps(data, ensure_ascii = False, indent = 2), encoding = "utf-8")
    logger.info("Расписание сохранено [%s]: %d пар", group_name, len(lessons))


def load_schedule(group_name: str) -> list[dict]:
    """Загрузить расписание группы, пустой список если файла нет"""

    path = _schedule_path(group_name)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding = "utf-8"))
        return data.get("lessons", [])
    except Exception:
        logger.exception("Ошибка чтения расписания [%s]", group_name)
        return []


def get_day_schedule(group_name: str, weekday: int, week_type: str) -> list[dict]:
    """Получить пары на конкретный день с учётом типа недели"""

    lessons = load_schedule(group_name)
    return sorted(
        [
            l for l in lessons
            if l["weekday"] == weekday
            and l["week_type"] in ("both", week_type)
        ],
        key = lambda l: l["lesson_number"],
    )


def get_full_schedule(group_name: str, week_type: str) -> dict[int, list[dict]]:
    """Всё расписание группы, сгруппированное по дням"""

    lessons = load_schedule(group_name)
    result: dict[int, list[dict]] = {}
    for day in range(6):
        day_lessons = sorted(
            [
                l for l in lessons
                if l["weekday"] == day
                and l["week_type"] in ("both", week_type)
            ],
            key = lambda l: l["lesson_number"],
        )
        if day_lessons:
            result[day] = day_lessons
    return result


# --- Реестр групп ---

def _load_groups_raw() -> dict:
    """Загрузить сырой JSON реестра групп"""

    if not GROUPS_PATH.exists():
        return {}
    try:
        return json.loads(GROUPS_PATH.read_text(encoding = "utf-8"))
    except Exception:
        logger.exception("Ошибка чтения groups.json")
        return {}


def _save_groups_raw(groups: dict) -> None:
    """Сохранить реестр групп"""

    DATA_DIR.mkdir(parents = True, exist_ok = True)
    GROUPS_PATH.write_text(json.dumps(groups, ensure_ascii = False, indent = 2), encoding = "utf-8")


def save_group(chat_id: int, group_name: str, semester_start: str, registered_by: int) -> None:
    """Зарегистрировать группу для чата"""

    groups = _load_groups_raw()
    groups[str(chat_id)] = {
        "group_name": group_name,
        "semester_start": semester_start,
        "registered_by": registered_by,
    }
    _save_groups_raw(groups)
    logger.info("Группа [%s] привязана к чату %d", group_name, chat_id)


def remove_group(chat_id: int) -> bool:
    """Отвязать группу от чата, возвращает True если была привязка"""

    groups = _load_groups_raw()
    if str(chat_id) in groups:
        del groups[str(chat_id)]
        _save_groups_raw(groups)
        return True
    return False


def load_groups() -> dict[int, dict]:
    """Загрузить все зарегистрированные группы: {chat_id: {group_name, semester_start, ...}}"""

    raw = _load_groups_raw()
    return {int(k): v for k, v in raw.items()}


def get_group_by_chat(chat_id: int) -> dict | None:
    """Получить конфиг группы по chat_id, None если не зарегистрирована"""

    groups = _load_groups_raw()
    return groups.get(str(chat_id))


def list_available_groups() -> list[str]:
    """Список доступных групп (по наличию файлов расписания)"""

    if not SCHEDULES_DIR.exists():
        return []
    groups = []
    for path in SCHEDULES_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding = "utf-8"))
            lessons = data.get("lessons", [])
            if lessons:
                groups.append(path.stem.replace("_", " ").strip())
        except Exception:
            continue
    return sorted(groups)
