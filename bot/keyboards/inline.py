"""Инлайн-клавиатуры с кнопкой WebApp и URL-ссылкой"""

from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo


def webapp_keyboard(base_url: str, week_type: str, group_name: str) -> InlineKeyboardMarkup:
    url = f"{base_url}?week={week_type}&group={quote(group_name)}"
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            web_app = WebAppInfo(url = url),
        )
    ]])


def url_keyboard(base_url: str, week_type: str, group_name: str) -> InlineKeyboardMarkup:
    url = f"{base_url}?week={week_type}&group={quote(group_name)}"
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            url = url,
        )
    ]])


def group_selection_keyboard(groups: list[str]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора группы при /register"""

    buttons = [
        [InlineKeyboardButton(text = name, callback_data = f"reg:{name}")]
        for name in groups
    ]
    return InlineKeyboardMarkup(inline_keyboard = buttons)
