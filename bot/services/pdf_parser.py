"""Парсер PDF-файлов с расписанием занятий"""

import re

from pathlib import Path

import pdfplumber

from bot.logger import get_logger


logger = get_logger(__name__)


# Соответствие времени начала → номер пары
LESSON_NUM_BY_START: dict[str, int] = {
    "09:00": 1,
    "10:55": 2,
    "13:00": 3,
    "14:55": 4,
    "16:50": 5,
    "18:30": 6,
    "20:15": 7,
}

DAY_NAMES: dict[str, int] = {
    "ПОНЕДЕЛЬНИК": 0,
    "ВТОРНИК": 1,
    "СРЕДА": 2,
    "ЧЕТВЕРГ": 3,
    "ПЯТНИЦА": 4,
    "СУББОТА": 5,
}

TYPE_MAP: dict[str, str] = {
    "лек": "Лекция",
    "пр": "Практика",
    "лаб": "Лабораторная",
}


def _parse_day_name(cell: str) -> int | None:
    """Распознать день недели из ячейки вида 'П\\nО\\nН\\nЕ\\nД...'"""

    if not cell:
        return None
    clean = cell.replace("\n", "").strip()
    for name, idx in DAY_NAMES.items():
        if clean == name:
            return idx
    return None


def _parse_time(cell: str) -> tuple[str, str]:
    """Распознать время из ячейки вида '09.00-\\n10.35' → ('09:00', '10:35')"""

    clean = cell.replace("\n", "").replace(" ", "").replace(".", ":")
    parts = clean.split("-")
    return parts[0], parts[1]


def _parse_cell(text: str) -> dict | None:
    """Распарсить содержимое ячейки расписания

    Формат: 'тип.Предмет\\nПРЕПОДАВАТЕЛЬ И.О. АУДИТОРИЯ'
    Возвращает dict с subject, lesson_type, teacher, room или None
    """

    if not text or not text.strip():
        return None

    # Склеиваем строки в одну
    full = " ".join(text.strip().splitlines())
    full = re.sub(r"\s+", " ", full).strip()
    # Убираем пробел после дефиса из-за переноса строки в PDF
    full = re.sub(r"- ", "-", full)

    # Определяем тип занятия по префиксу
    lesson_type = "Другое"
    for prefix, name in TYPE_MAP.items():
        if full.lower().startswith(prefix + "."):
            lesson_type = name
            full = full[len(prefix) + 1 :].strip()
            break

    # Ищем преподавателя: ФАМИЛИЯ И.О. (кириллица, всё заглавные)
    teacher_match = re.search(r"([А-ЯЁ]{2,})\s+([А-ЯЁ]\.[А-ЯЁ]\.)", full)

    teacher: str | None = None
    subject: str = full
    room: str | None = None

    if teacher_match:
        teacher = f"{teacher_match.group(1)} {teacher_match.group(2)}"
        subject = full[: teacher_match.start()].strip()
        rest = full[teacher_match.end() :].strip()
        if rest:
            room = rest
    else:
        # Нет преподавателя — ищем аудиторию в конце
        room_match = re.search(r"((?:\d{1,2}-\S+\s*)+)$", full)
        if room_match:
            room = room_match.group(1).strip()
            subject = full[: room_match.start()].strip()
        elif full.rstrip().endswith("СК"):
            room = "СК"
            subject = full[:-2].strip()

    if not subject:
        return None

    return {
        "subject": subject,
        "lesson_type": lesson_type,
        "teacher": teacher,
        "room": room,
    }


def parse_pdf(file_path: str, group_name: str) -> list[dict]:
    """Распарсить PDF расписания и вернуть список пар для указанной группы

    Возвращает list[dict] с ключами:
    weekday, week_type, lesson_number, time_start, time_end,
    subject, lesson_type, teacher, room, subgroup
    """

    lessons: list[dict] = []
    path = Path(file_path)

    if not path.exists():
        logger.error("Файл не найден: %s", file_path)
        return []

    logger.info("Парсинг PDF: %s, группа: %s", file_path, group_name)

    try:
        pdf = pdfplumber.open(str(path))
    except Exception:
        logger.exception("Не удалось открыть PDF: %s", file_path)
        return []

    try:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = table[0]
                # Ищем столбец нужной группы
                col_idx: int | None = None
                for ci, cell in enumerate(header):
                    if cell and group_name in cell:
                        col_idx = ci
                        break

                if col_idx is None:
                    continue

                logger.info(
                    "Стр. %d: найдена группа '%s' в столбце %d",
                    page_idx, group_name, col_idx,
                )

                # Собираем временные слоты
                time_slots: list[dict] = []
                current_day: int = 0

                for row in table[1:]:
                    day_cell = row[0]
                    time_cell = row[1]
                    group_cell = row[col_idx] if col_idx < len(row) else None

                    # Определяем день
                    if day_cell:
                        parsed_day = _parse_day_name(day_cell)
                        if parsed_day is not None:
                            current_day = parsed_day

                    if time_cell:
                        # Новый временной слот
                        try:
                            t_start, t_end = _parse_time(time_cell)
                        except (IndexError, ValueError):
                            logger.warning("Не удалось распознать время: %s", time_cell)
                            continue

                        lesson_num = LESSON_NUM_BY_START.get(t_start, 0)
                        time_slots.append({
                            "day": current_day,
                            "time_start": t_start,
                            "time_end": t_end,
                            "lesson_num": lesson_num,
                            "cells": [group_cell],
                        })
                    else:
                        # Продолжение предыдущего слота (вторая строка = чёт/нечёт)
                        if time_slots:
                            time_slots[-1]["cells"].append(group_cell)

                # Обрабатываем каждый временной слот
                for slot in time_slots:
                    cells = slot["cells"]
                    day = slot["day"]
                    t_start = slot["time_start"]
                    t_end = slot["time_end"]
                    lesson_num = slot["lesson_num"]

                    if len(cells) == 1:
                        # Одна строка — обе недели
                        parsed = _parse_cell(cells[0])
                        if parsed:
                            lessons.append(_make_lesson(
                                day, "both", lesson_num, t_start, t_end, parsed
                            ))
                    elif len(cells) >= 2:
                        odd_cell = cells[0]
                        even_cell = cells[1]

                        if even_cell is None:
                            # Ячейка объединена — обе недели
                            parsed = _parse_cell(odd_cell)
                            if parsed:
                                lessons.append(_make_lesson(
                                    day, "both", lesson_num, t_start, t_end, parsed
                                ))
                        elif odd_cell == even_cell:
                            # Одинаковое содержимое — обе недели
                            parsed = _parse_cell(odd_cell)
                            if parsed:
                                lessons.append(_make_lesson(
                                    day, "both", lesson_num, t_start, t_end, parsed
                                ))
                        else:
                            # Разное содержимое — числитель/знаменатель
                            parsed_odd = _parse_cell(odd_cell)
                            if parsed_odd:
                                lessons.append(_make_lesson(
                                    day, "odd", lesson_num, t_start, t_end, parsed_odd
                                ))
                            parsed_even = _parse_cell(even_cell)
                            if parsed_even:
                                lessons.append(_make_lesson(
                                    day, "even", lesson_num, t_start, t_end, parsed_even
                                ))
    except Exception:
        logger.exception("Ошибка при парсинге PDF")
    finally:
        pdf.close()

    logger.info("Всего распарсено пар: %d", len(lessons))
    return lessons


def parse_pdf_all_groups(file_path: str) -> dict[str, list[dict]]:
    """Распарсить PDF и вернуть расписание для ВСЕХ найденных групп

    Возвращает dict: {group_name: [lessons]}
    """

    path = Path(file_path)
    if not path.exists():
        logger.error("Файл не найден: %s", file_path)
        return {}

    logger.info("Парсинг PDF (все группы): %s", file_path)

    try:
        pdf = pdfplumber.open(str(path))
    except Exception:
        logger.exception("Не удалось открыть PDF: %s", file_path)
        return {}

    # Находим все группы в заголовках
    group_names: list[str] = []
    try:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header = table[0]
                for cell in header:
                    if cell and cell.strip() and cell.strip() not in group_names:
                        clean = cell.strip()
                        if re.match(r"^[А-ЯЁа-яё]+-[А-ЯЁа-яё]+\s+\d+", clean):
                            group_names.append(clean)
    except Exception:
        logger.exception("Ошибка при поиске групп в PDF")
    finally:
        pdf.close()

    logger.info("Найдено групп в PDF: %d — %s", len(group_names), ", ".join(group_names))

    result: dict[str, list[dict]] = {}
    for name in group_names:
        lessons = parse_pdf(file_path, name)
        if lessons:
            result[name] = lessons

    return result


def _make_lesson(
    weekday: int,
    week_type: str,
    lesson_number: int,
    time_start: str,
    time_end: str,
    parsed: dict,
) -> dict:

    return {
        "weekday": weekday,
        "week_type": week_type,
        "lesson_number": lesson_number,
        "time_start": time_start,
        "time_end": time_end,
        "subject": parsed["subject"],
        "lesson_type": parsed["lesson_type"],
        "teacher": parsed["teacher"],
        "room": parsed["room"],
        "subgroup": None,
    }
