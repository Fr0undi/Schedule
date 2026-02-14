"""Inline-клавиатуры для загрузки PDF с выбором иерархии"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def upload_forms_kb(forms: list[dict]) -> InlineKeyboardMarkup:
    """Кнопки форм обучения"""

    buttons = [
        [InlineKeyboardButton(text = f["name"], callback_data = f"up:f:{f['code']}")]
        for f in forms
    ]
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def upload_institutes_kb(institutes: list[dict], form_code: str) -> InlineKeyboardMarkup:
    """Кнопки институтов"""

    buttons = [
        [InlineKeyboardButton(text = inst["name"], callback_data = f"up:i:{form_code}:{inst['code']}")]
        for inst in institutes
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = "up:forms")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def upload_levels_kb(levels: list[dict], form_code: str, inst_code: str) -> InlineKeyboardMarkup:
    """Кнопки уровней обучения"""

    buttons = [
        [InlineKeyboardButton(text = lv["name"], callback_data = f"up:l:{form_code}:{inst_code}:{lv['code']}")]
        for lv in levels
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = f"up:f:{form_code}")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def upload_courses_kb(courses: list[int], form_code: str, inst_code: str, level_code: str) -> InlineKeyboardMarkup:
    """Кнопки курсов"""

    buttons = [
        [InlineKeyboardButton(text = f"{c} курс", callback_data = f"up:c:{form_code}:{inst_code}:{level_code}:{c}")]
        for c in courses
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = f"up:i:{form_code}:{inst_code}")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)
