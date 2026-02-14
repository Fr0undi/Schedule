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
UNIVERSITY_PATH = DATA_DIR / "university.json"


def _slugify(group_name: str) -> str:
    """Преобразовать название группы в безопасное имя файла"""

    return re.sub(r"[^\w\-]", "_", group_name).strip("_")


def _find_schedule_path(group_name: str) -> Path | None:
    """Найти существующий файл расписания группы (рекурсивный поиск)"""

    if not SCHEDULES_DIR.exists():
        return None
    filename = f"{_slugify(group_name)}.json"
    for path in SCHEDULES_DIR.rglob(filename):
        return path
    return None


def _build_schedule_path(
    group_name: str,
    form: str | None = None,
    institute: str | None = None,
    course: int | None = None,
) -> Path:
    """Построить путь к файлу: schedules/{form}/{institute}/{course}/{slug}.json"""

    slug = _slugify(group_name)
    if form and institute and course is not None:
        return SCHEDULES_DIR / form / institute / str(course) / f"{slug}.json"
    return SCHEDULES_DIR / f"{slug}.json"


# --- Расписание ---

def load_schedule_meta(group_name: str) -> dict | None:
    """Загрузить полный JSON расписания (с метаданными), None если файла нет"""

    path = _find_schedule_path(group_name)
    if not path:
        return None
    try:
        return json.loads(path.read_text(encoding = "utf-8"))
    except Exception:
        logger.exception("Ошибка чтения расписания [%s]", group_name)
        return None


def save_schedule(
    group_name: str,
    lessons: list[dict],
    form: str | None = None,
    institute: str | None = None,
    level: str | None = None,
    course: int | None = None,
) -> None:
    """Сохранить расписание для конкретной группы с метаданными"""

    lessons.sort(key = lambda l: (l["weekday"], l["lesson_number"]))

    # Сохранить существующие метаданные если новые не переданы
    if form is None and institute is None and level is None and course is None:
        existing = load_schedule_meta(group_name)
        if existing:
            form = existing.get("form")
            institute = existing.get("institute")
            level = existing.get("level")
            course = existing.get("course")

    data = {
        "updated_at": datetime.now().isoformat(),
        "group_name": group_name,
        "form": form,
        "institute": institute,
        "level": level,
        "course": course,
        "lessons": lessons,
    }

    # Удалить старый файл если он в другом месте
    old_path = _find_schedule_path(group_name)
    new_path = _build_schedule_path(group_name, form, institute, course)

    if old_path and old_path != new_path:
        old_path.unlink(missing_ok = True)

    new_path.parent.mkdir(parents = True, exist_ok = True)
    new_path.write_text(json.dumps(data, ensure_ascii = False, indent = 2), encoding = "utf-8")
    logger.info("Расписание сохранено [%s]: %s", group_name, new_path.relative_to(SCHEDULES_DIR))


def load_schedule(group_name: str) -> list[dict]:
    """Загрузить расписание группы, пустой список если файла нет"""

    path = _find_schedule_path(group_name)
    if not path:
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
    for day in range(1, 7):
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
    """Список доступных групп (рекурсивный поиск)"""

    if not SCHEDULES_DIR.exists():
        return []
    groups = []
    for path in SCHEDULES_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding = "utf-8"))
            if data.get("lessons"):
                name = data.get("group_name") or path.stem.replace("_", " ").strip()
                groups.append(name)
        except Exception:
            continue
    return sorted(groups)


# --- Университет ---

def load_university() -> dict:
    """Загрузить структуру университета из university.json"""

    if not UNIVERSITY_PATH.exists():
        return {"forms": []}
    try:
        return json.loads(UNIVERSITY_PATH.read_text(encoding = "utf-8"))
    except Exception:
        logger.exception("Ошибка чтения university.json")
        return {"forms": []}


def list_groups_filtered(
    form: str | None = None,
    institute: str | None = None,
    level: str | None = None,
    course: int | None = None,
) -> list[str]:
    """Отфильтровать доступные группы по иерархии (через директории)"""

    if not SCHEDULES_DIR.exists():
        return []

    # Сужаем директорию поиска по известным параметрам
    search_dir = SCHEDULES_DIR
    if form:
        search_dir = search_dir / form
        if institute:
            search_dir = search_dir / institute
            if course is not None:
                search_dir = search_dir / str(course)

    if not search_dir.exists():
        return []

    groups = []
    for path in search_dir.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding = "utf-8"))
            if not data.get("lessons"):
                continue
            if level and data.get("level") != level:
                continue
            name = data.get("group_name") or path.stem.replace("_", " ").strip()
            groups.append(name)
        except Exception:
            continue
    return sorted(groups)
