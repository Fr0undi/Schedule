"""Inline-клавиатуры для регистрации группы"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def register_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню /register: поиск или пошагово"""

    return InlineKeyboardMarkup(inline_keyboard = [
        [InlineKeyboardButton(text = "🔍 Поиск по названию", callback_data = "rg:search")],
        [InlineKeyboardButton(text = "📋 Выбрать по структуре", callback_data = "rg:step")],
    ])


def register_forms_kb(forms: list[dict]) -> InlineKeyboardMarkup:
    """Кнопки форм обучения"""

    buttons = [
        [InlineKeyboardButton(text = f["name"], callback_data = f"rg:f:{f['code']}")]
        for f in forms
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = "rg:menu")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def register_institutes_kb(institutes: list[dict], form_code: str) -> InlineKeyboardMarkup:
    """Кнопки институтов"""

    buttons = [
        [InlineKeyboardButton(text = inst["name"], callback_data = f"rg:i:{form_code}:{inst['code']}")]
        for inst in institutes
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = "rg:step")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def register_levels_kb(levels: list[dict], form_code: str, inst_code: str) -> InlineKeyboardMarkup:
    """Кнопки уровней обучения"""

    buttons = [
        [InlineKeyboardButton(text = lv["name"], callback_data = f"rg:l:{form_code}:{inst_code}:{lv['code']}")]
        for lv in levels
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = f"rg:f:{form_code}")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def register_courses_kb(courses: list[int], form_code: str, inst_code: str, level_code: str) -> InlineKeyboardMarkup:
    """Кнопки курсов"""

    buttons = [
        [InlineKeyboardButton(text = f"{c} курс", callback_data = f"rg:c:{form_code}:{inst_code}:{level_code}:{c}")]
        for c in courses
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = f"rg:i:{form_code}:{inst_code}")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def register_groups_kb(groups: list[str]) -> InlineKeyboardMarkup:
    """Кнопки доступных групп"""

    buttons = [
        [InlineKeyboardButton(text = name, callback_data = f"rg:g:{name}")]
        for name in groups
    ]
    buttons.append([InlineKeyboardButton(text = "« Назад", callback_data = "rg:menu")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)


def search_results_kb(groups: list[str]) -> InlineKeyboardMarkup:
    """Результаты поиска групп"""

    buttons = [
        [InlineKeyboardButton(text = name, callback_data = f"rg:g:{name}")]
        for name in groups
    ]
    buttons.append([InlineKeyboardButton(text = "🔍 Новый поиск", callback_data = "rg:search")])
    buttons.append([InlineKeyboardButton(text = "« В меню", callback_data = "rg:menu")])
    return InlineKeyboardMarkup(inline_keyboard = buttons)
