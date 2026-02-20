"""Хранение и загрузка расписания в формате JSON"""

import json
import re

from pathlib import Path
from datetime import datetime, timezone, timedelta

_MSK = timezone(timedelta(hours = 3))

from bot.config import settings

from bot.logger import get_logger


logger = get_logger(__name__)

DATA_DIR = Path(settings.DATA_DIR)
SCHEDULES_DIR = DATA_DIR / "schedules"
GROUPS_PATH = DATA_DIR / "groups.json"
UNIVERSITY_PATH = DATA_DIR / "university.json"
BINDINGS_LOG_PATH = DATA_DIR / "bindings_log.json"


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
        "updated_at": datetime.now(_MSK).isoformat(),
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
    invalidate_teacher_cache()


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


def _log_binding(action: str, chat_id: int, user_id: int, **kwargs) -> None:
    """Записать событие привязки/отвязки в журнал"""

    entry = {
        "action": action,
        "chat_id": chat_id,
        "user_id": user_id,
        "timestamp": datetime.now(_MSK).isoformat(),
        **kwargs,
    }

    log: list[dict] = []
    if BINDINGS_LOG_PATH.exists():
        try:
            log = json.loads(BINDINGS_LOG_PATH.read_text(encoding = "utf-8"))
        except Exception:
            pass

    log.append(entry)
    DATA_DIR.mkdir(parents = True, exist_ok = True)
    BINDINGS_LOG_PATH.write_text(json.dumps(log, ensure_ascii = False, indent = 2), encoding = "utf-8")


def save_group(chat_id: int, group_name: str, semester_start: str, registered_by: int) -> None:
    """Зарегистрировать группу для чата"""

    groups = _load_groups_raw()
    old = groups.get(str(chat_id), {})
    groups[str(chat_id)] = {
        "group_name": group_name,
        "semester_start": semester_start,
        "registered_by": registered_by,
        "registered_at": datetime.now(_MSK).isoformat(),
        "topic_id": old.get("topic_id"),
    }
    _save_groups_raw(groups)
    _log_binding("bind", chat_id, registered_by, group_name = group_name)
    logger.info("Группа [%s] привязана к чату %d", group_name, chat_id)


def save_teacher_binding(chat_id: int, teacher_name: str, semester_start: str, registered_by: int) -> None:
    """Зарегистрировать преподавателя для чата (вместо группы)"""

    groups = _load_groups_raw()
    old = groups.get(str(chat_id), {})
    groups[str(chat_id)] = {
        "teacher_name": teacher_name,
        "semester_start": semester_start,
        "registered_by": registered_by,
        "registered_at": datetime.now(_MSK).isoformat(),
        "topic_id": old.get("topic_id"),
    }
    _save_groups_raw(groups)
    _log_binding("bind", chat_id, registered_by, teacher_name = teacher_name)
    logger.info("Преподаватель [%s] привязан к чату %d", teacher_name, chat_id)


def save_topic(chat_id: int, topic_id: int | None) -> bool:
    """Привязать тему (topic) для ежедневной рассылки. None — сбросить."""

    groups = _load_groups_raw()
    key = str(chat_id)
    if key not in groups:
        return False
    groups[key]["topic_id"] = topic_id
    _save_groups_raw(groups)
    return True


def remove_group(chat_id: int, removed_by: int = 0) -> bool:
    """Отвязать расписание от чата, возвращает True если была привязка"""

    groups = _load_groups_raw()
    key = str(chat_id)
    if key in groups:
        old = groups[key]
        name = old.get("teacher_name") or old.get("group_name", "?")
        log_kwargs = {}
        if old.get("teacher_name"):
            log_kwargs["teacher_name"] = old["teacher_name"]
        else:
            log_kwargs["group_name"] = old.get("group_name", "?")

        del groups[key]
        _save_groups_raw(groups)
        _log_binding("unbind", chat_id, removed_by, **log_kwargs)
        logger.info("Расписание [%s] отвязано от чата %d", name, chat_id)
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
            if "lessons" not in data:
                continue
            name = data.get("group_name") or path.stem.replace("_", " ").strip()
            groups.append(name)
        except Exception:
            continue
    return sorted(groups)


def list_groups_structured() -> list[dict]:
    """Группы, сгруппированные по институтам и курсам.

    Возвращает: [{name: "Институт ...", courses: [{course: 1, groups: [...]}, ...]}, ...]
    """

    if not SCHEDULES_DIR.exists():
        return []

    # Загрузить названия институтов из university.json
    uni = load_university()
    inst_names: dict[str, str] = {}
    for form in uni.get("forms", []):
        for inst in form.get("institutes", []):
            inst_names[inst["code"]] = inst["name"]

    # Собрать группы с метаданными
    by_inst: dict[str, dict[int, list[str]]] = {}
    for path in SCHEDULES_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding = "utf-8"))
            if "lessons" not in data:
                continue
            name = data.get("group_name") or path.stem.replace("_", " ").strip()
            institute = data.get("institute", "other")
            course = data.get("course", 0)
            by_inst.setdefault(institute, {}).setdefault(course, []).append(name)
        except Exception:
            continue

    # Сформировать результат
    result = []
    for inst_code in sorted(by_inst.keys(), key = lambda c: inst_names.get(c, c)):
        courses = []
        for course_num in sorted(by_inst[inst_code].keys()):
            groups = sorted(by_inst[inst_code][course_num])
            courses.append({"course": course_num, "groups": groups})
        result.append({
            "name": inst_names.get(inst_code, inst_code),
            "code": inst_code,
            "courses": courses,
        })
    return result


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
            if "lessons" not in data:
                continue
            if level and data.get("level") != level:
                continue
            name = data.get("group_name") or path.stem.replace("_", " ").strip()
            groups.append(name)
        except Exception:
            continue
    return sorted(groups)


# --- Преподаватели ---

_teacher_cache: dict[str, list[dict]] | None = None


def _normalize_teacher(name: str) -> str:
    """Нормализация ФИО: убрать пробелы, привести регистр, гарантировать точку в конце.

    'КУКАРЦЕВ В.В.' и 'кукарцев в.в.' → 'Кукарцев В.В.'
    """

    name = name.strip().rstrip(".")
    # "КУКАРЦЕВ В.В" → ["КУКАРЦЕВ", "В.В"]
    parts = name.split()
    normalized = []
    for p in parts:
        # Инициалы ("В.В", "А.") — каждую букву заглавной
        if "." in p or (len(p) <= 4 and p.replace(".", "").isalpha()):
            normalized.append(p.upper())
        else:
            # Фамилия — первая заглавная, остальные строчные
            normalized.append(p.capitalize())
    return " ".join(normalized) + "."


def _build_teacher_index() -> dict[str, list[dict]]:
    """Построить индекс {ФИО: [lesson+group_name, ...]} из всех расписаний"""

    global _teacher_cache
    if _teacher_cache is not None:
        return _teacher_cache

    index: dict[str, list[dict]] = {}
    if not SCHEDULES_DIR.exists():
        _teacher_cache = {}
        return _teacher_cache

    for path in SCHEDULES_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding = "utf-8"))
            if "lessons" not in data:
                continue
            group_name = data.get("group_name") or path.stem.replace("_", " ").strip()
            for lesson in data["lessons"]:
                teacher = lesson.get("teacher")
                if not teacher:
                    continue
                normalized = _normalize_teacher(teacher)
                enriched = {**lesson, "group_name": group_name}
                index.setdefault(normalized, []).append(enriched)
        except Exception:
            continue

    _teacher_cache = index
    return _teacher_cache


def invalidate_teacher_cache() -> None:
    """Сбросить кэш преподавателей (вызывать после изменения расписаний)"""

    global _teacher_cache
    _teacher_cache = None


def list_available_teachers() -> list[str]:
    """Отсортированный список всех уникальных преподавателей"""

    index = _build_teacher_index()
    return sorted(index.keys())


def _merge_teacher_lessons(lessons: list[dict]) -> list[dict]:
    """Объединить пары с одинаковым временем/предметом/типом (поток → одна пара)"""

    merged: dict[tuple, dict] = {}
    for l in lessons:
        key = (l["weekday"], l["lesson_number"], l["week_type"], l["subject"], l["lesson_type"])
        if key in merged:
            existing = merged[key]
            if l["group_name"] not in existing["group_name"]:
                existing["group_name"] += "; " + l["group_name"]
            if l.get("room") and l["room"] not in (existing.get("room") or ""):
                existing["room"] = (existing.get("room") or "") + "; " + l["room"]
        else:
            merged[key] = {**l}
    return list(merged.values())


def get_teacher_day_schedule(teacher_name: str, weekday: int, week_type: str) -> list[dict]:
    """Получить пары преподавателя на конкретный день"""

    index = _build_teacher_index()
    lessons = index.get(teacher_name, [])
    filtered = [
        l for l in lessons
        if l["weekday"] == weekday and l["week_type"] in ("both", week_type)
    ]
    merged = _merge_teacher_lessons(filtered)
    return sorted(merged, key = lambda l: l["lesson_number"])


def get_teacher_full_schedule(teacher_name: str, week_type: str) -> dict[int, list[dict]]:
    """Расписание преподавателя, сгруппированное по дням"""

    index = _build_teacher_index()
    lessons = index.get(teacher_name, [])
    filtered = [
        l for l in lessons
        if l["week_type"] in ("both", week_type)
    ]
    merged = _merge_teacher_lessons(filtered)
    result: dict[int, list[dict]] = {}
    for day in range(1, 7):
        day_lessons = sorted(
            [l for l in merged if l["weekday"] == day],
            key = lambda l: l["lesson_number"],
        )
        if day_lessons:
            result[day] = day_lessons
    return result
