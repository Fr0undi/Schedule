"""Утилиты для определения номера и типа учебной недели"""

from datetime import date


def get_week_number(target_date: date, semester_start: str) -> int:
    """Номер учебной недели от начала семестра (1-based)"""

    start = date.fromisoformat(semester_start)
    delta = (target_date - start).days
    return delta // 7 + 1


def get_week_type(target_date: date, semester_start: str) -> str:
    """'odd' (нечётная/числитель) или 'even' (чётная/знаменатель)"""

    week_num = get_week_number(target_date, semester_start)
    return "odd" if week_num % 2 == 1 else "even"


def get_week_type_display(week_type: str) -> str:
    return "Нечётная (числитель)" if week_type == "odd" else "Чётная (знаменатель)"
