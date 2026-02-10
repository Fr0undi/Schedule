"""Инлайн-клавиатуры с кнопкой WebApp и URL-ссылкой"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo


def webapp_keyboard(base_url: str, week_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            web_app = WebAppInfo(url = f"{base_url}?week={week_type}"),
        )
    ]])


def url_keyboard(base_url: str, week_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard = [[
        InlineKeyboardButton(
            text = "📱 Полное расписание",
            url = f"{base_url}?week={week_type}",
        )
    ]])
